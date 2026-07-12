"""Run the real-audio Databricks IELTS demo with non-mock ASR."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ielts_scorer.asr import LocalWhisperASRClient
from ielts_scorer.audio_ingest import (
    DEFAULT_VOLUME_PATH,
    guard_real_audio_required,
    upload_to_databricks_volume,
    validate_audio_file,
    volume_destination,
)
from ielts_scorer.audio_preprocess import inspect_audio, preprocess_for_asr
from ielts_scorer.features import extract_features
from ielts_scorer.provider_provenance import registered_real_audio_provenance
from ielts_scorer.report import write_report_files
from ielts_scorer.schemas import Attempt
from ielts_scorer.scoring import build_mock_report
from scripts.register_real_audio_attempt import run_statement, sql_literal

WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID", "77cea25dcd8171c6")
NAMESPACE = os.getenv("DATABRICKS_NAMESPACE", "main.ielts_demo")


def insert_row(table: str, columns: list[str], values: list[Any]) -> None:
    run_statement(
        f"INSERT INTO {NAMESPACE}.{table} ({', '.join(columns)}) "
        f"VALUES ({', '.join(sql_literal(value) for value in values)})"
    )


def delete_attempt_outputs(attempt_id: str) -> None:
    for table in ("attempts", "asr_segments", "speech_features", "scoring_results", "processing_runs"):
        run_statement(f"DELETE FROM {NAMESPACE}.{table} WHERE attempt_id = {sql_literal(attempt_id)}")


def insert_attempt(attempt: Attempt) -> None:
    insert_row(
        "attempts",
        [
            "attempt_id",
            "candidate_id",
            "question_id",
            "question_text",
            "audio_path",
            "audio_format",
            "duration_sec",
            "source",
            "created_at",
        ],
        [
            attempt.attempt_id,
            attempt.candidate_id,
            attempt.question_id,
            attempt.question_text,
            attempt.audio_path,
            attempt.audio_format,
            attempt.duration_sec,
            attempt.source,
            attempt.created_at,
        ],
    )


def insert_processing_run(
    attempt_id: str,
    audio_path: str,
    audio_sha256: str,
    audio_size_bytes: int,
    status: str,
    error_message: str = "",
) -> None:
    insert_row(
        "processing_runs",
        [
            "run_id",
            "attempt_id",
            "pipeline_mode",
            "audio_path",
            "audio_exists",
            "audio_sha256",
            "audio_size_bytes",
            "asr_provider",
            "asr_is_mock",
            "scoring_provider",
            "scoring_is_mock",
            "processing_status",
            "error_message",
            "created_at",
        ],
        [
            f"run_{uuid.uuid4().hex}",
            attempt_id,
            "real_audio",
            audio_path,
            True,
            audio_sha256,
            audio_size_bytes,
            "local_whisper",
            False,
            "rule_based_mock",
            True,
            status,
            error_message,
            datetime.now(timezone.utc),
        ],
    )


def insert_segments(attempt_id: str, segments) -> None:
    for segment in segments:
        insert_row(
            "asr_segments",
            [
                "attempt_id",
                "segment_id",
                "start_sec",
                "end_sec",
                "text",
                "avg_logprob",
                "no_speech_prob",
                "created_at",
            ],
            [
                attempt_id,
                segment.segment_id,
                segment.start_sec,
                segment.end_sec,
                segment.text,
                segment.avg_logprob,
                segment.no_speech_prob,
                segment.created_at,
            ],
        )


def insert_features(features) -> None:
    insert_row(
        "speech_features",
        [
            "attempt_id",
            "duration_sec",
            "speaking_sec",
            "silence_ratio",
            "words_count",
            "words_per_min",
            "pause_count",
            "long_pause_count",
            "avg_pause_sec",
            "filler_count",
            "filler_ratio",
            "repetition_count",
            "lexical_diversity",
            "avg_sentence_len",
            "complex_sentence_proxy",
            "asr_confidence_proxy",
            "created_at",
        ],
        [
            features.attempt_id,
            features.duration_sec,
            features.speaking_sec,
            features.silence_ratio,
            features.words_count,
            features.words_per_min,
            features.pause_count,
            features.long_pause_count,
            features.avg_pause_sec,
            features.filler_count,
            features.filler_ratio,
            features.repetition_count,
            features.lexical_diversity,
            features.avg_sentence_len,
            features.complex_sentence_proxy,
            features.asr_confidence_proxy,
            features.created_at,
        ],
    )


def insert_report(report) -> None:
    record = report.to_scoring_result_record()
    columns = list(record)
    insert_row("scoring_results", columns, [record[column] for column in columns])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real-audio IELTS demo with Local Whisper ASR.")
    parser.add_argument("--audio-path", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--question-id", required=True)
    parser.add_argument("--question-text", required=True)
    parser.add_argument("--volume-path", default=os.getenv("DATABRICKS_VOLUME_PATH", DEFAULT_VOLUME_PATH))
    parser.add_argument("--output-dir", default=os.getenv("OUTPUT_DIR", "outputs"))
    parser.add_argument("--processed-dir", default=os.getenv("PROCESSED_AUDIO_DIR", "outputs/processed_audio"))
    parser.add_argument("--whisper-model", default=os.getenv("WHISPER_MODEL", "tiny.en"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.getenv("MOCK_ASR", "false").strip().lower() in {"1", "true", "yes", "on"}:
        raise SystemExit("ERROR: run_real_audio_demo.py requires MOCK_ASR=false")
    asr_provider = os.getenv("ASR_PROVIDER", "local_whisper").strip().lower()
    if asr_provider == "mock":
        raise SystemExit("ERROR: run_real_audio_demo.py requires non-mock ASR")
    if asr_provider != "local_whisper":
        raise SystemExit(f"ERROR: unsupported ASR_PROVIDER={asr_provider}; expected local_whisper")

    local_audio = Path(args.audio_path).expanduser().resolve()
    guard_real_audio_required(local_audio, real_audio_required=True, asr_provider=asr_provider)
    audio_metadata = validate_audio_file(local_audio, require_wav_for_real_asr=True)
    inspection = inspect_audio(local_audio)
    processed_audio = preprocess_for_asr(local_audio, Path(args.processed_dir))
    processed_inspection = inspect_audio(processed_audio)
    volume_audio_path = upload_to_databricks_volume(
        local_audio,
        volume_destination(args.attempt_id, local_audio, args.volume_path),
    )

    attempt = Attempt(
        attempt_id=args.attempt_id,
        candidate_id=args.candidate_id,
        question_id=args.question_id,
        question_text=args.question_text,
        audio_path=volume_audio_path,
        audio_format=audio_metadata.audio_format,
        duration_sec=processed_inspection.duration_sec,
        source="upload",
    )

    delete_attempt_outputs(args.attempt_id)
    insert_attempt(attempt)
    insert_processing_run(
        attempt_id=args.attempt_id,
        audio_path=volume_audio_path,
        audio_sha256=audio_metadata.audio_sha256,
        audio_size_bytes=audio_metadata.audio_size_bytes,
        status="REGISTERED",
    )

    asr_attempt = attempt.model_copy(update={"audio_path": str(processed_audio)})
    segments = LocalWhisperASRClient(model_name=args.whisper_model).transcribe(asr_attempt)
    nonempty_segments = [segment for segment in segments if segment.text.strip()]
    if not nonempty_segments:
        insert_processing_run(
            attempt_id=args.attempt_id,
            audio_path=volume_audio_path,
            audio_sha256=audio_metadata.audio_sha256,
            audio_size_bytes=audio_metadata.audio_size_bytes,
            status="FAILED",
            error_message="real ASR returned empty transcript",
        )
        raise SystemExit("ERROR: real ASR returned empty transcript")

    features = extract_features(args.attempt_id, nonempty_segments, duration_sec=processed_inspection.duration_sec)
    provenance = registered_real_audio_provenance(
        asr_provider="local_whisper",
        asr_is_mock=False,
        scoring_provider="rule_based_mock",
        scoring_is_mock=True,
    )
    report = build_mock_report(attempt, nonempty_segments, features, provenance=provenance)

    insert_segments(args.attempt_id, nonempty_segments)
    insert_features(features)
    insert_report(report)
    insert_processing_run(
        attempt_id=args.attempt_id,
        audio_path=volume_audio_path,
        audio_sha256=audio_metadata.audio_sha256,
        audio_size_bytes=audio_metadata.audio_size_bytes,
        status="COMPLETED",
    )
    json_path, markdown_path = write_report_files(report, Path(args.output_dir))

    print(f"attempt_id={args.attempt_id}")
    print(f"audio_path={volume_audio_path}")
    print(f"processed_audio={processed_audio}")
    print(f"original_duration_sec={inspection.duration_sec}")
    print(f"processed_duration_sec={processed_inspection.duration_sec}")
    print("asr_provider=local_whisper")
    print("asr_is_mock=false")
    print("scoring_provider=rule_based_mock")
    print("scoring_is_mock=true")
    print(f"segments={len(nonempty_segments)}")
    print(f"words={features.words_count}")
    print(f"overall_band={report.overall_band:.1f}")
    print(f"json_report={json_path}")
    print(f"markdown_report={markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
