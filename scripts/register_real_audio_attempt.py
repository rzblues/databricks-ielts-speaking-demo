"""Register a real audio attempt in Databricks metadata tables."""

from __future__ import annotations

import argparse
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ielts_scorer.audio_ingest import (
    DEFAULT_VOLUME_PATH,
    guard_real_audio_required,
    upload_to_databricks_volume,
    validate_audio_file,
    volume_destination,
)
from ielts_scorer.databricks_sql import NAMESPACE, run_statement, sql_literal
from ielts_scorer.schemas import Attempt

def ensure_processing_runs_table() -> None:
    run_statement(
        f"""
        CREATE TABLE IF NOT EXISTS {NAMESPACE}.processing_runs (
          run_id STRING,
          attempt_id STRING,
          pipeline_mode STRING,
          audio_path STRING,
          audio_exists BOOLEAN,
          audio_sha256 STRING,
          audio_size_bytes BIGINT,
          asr_provider STRING,
          asr_is_mock BOOLEAN,
          scoring_provider STRING,
          scoring_is_mock BOOLEAN,
          processing_status STRING,
          error_message STRING,
          created_at TIMESTAMP
        ) USING DELTA
        """
    )


def insert_attempt(attempt: Attempt) -> None:
    run_statement(f"DELETE FROM {NAMESPACE}.attempts WHERE attempt_id = {sql_literal(attempt.attempt_id)}")
    values = [
        attempt.attempt_id,
        attempt.candidate_id,
        attempt.question_id,
        attempt.question_text,
        attempt.audio_path,
        attempt.audio_format,
        attempt.duration_sec,
        attempt.source,
        attempt.created_at,
    ]
    run_statement(
        f"""
        INSERT INTO {NAMESPACE}.attempts
        (attempt_id, candidate_id, question_id, question_text, audio_path, audio_format, duration_sec, source, created_at)
        VALUES ({", ".join(sql_literal(value) for value in values)})
        """
    )


def insert_processing_run(
    attempt_id: str,
    audio_path: str,
    audio_sha256: str,
    audio_size_bytes: int,
    asr_provider: str,
    asr_is_mock: bool,
    scoring_provider: str,
    scoring_is_mock: bool,
    status: str,
    error_message: str = "",
) -> str:
    run_id = f"run_{uuid.uuid4().hex}"
    values = [
        run_id,
        attempt_id,
        "real_audio",
        audio_path,
        True,
        audio_sha256,
        audio_size_bytes,
        asr_provider,
        asr_is_mock,
        scoring_provider,
        scoring_is_mock,
        status,
        error_message,
        datetime.now(timezone.utc),
    ]
    run_statement(
        f"""
        INSERT INTO {NAMESPACE}.processing_runs
        (run_id, attempt_id, pipeline_mode, audio_path, audio_exists, audio_sha256, audio_size_bytes,
         asr_provider, asr_is_mock, scoring_provider, scoring_is_mock, processing_status, error_message, created_at)
        VALUES ({", ".join(sql_literal(value) for value in values)})
        """
    )
    return run_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register a real audio attempt for the Databricks IELTS demo.")
    parser.add_argument("--audio-path", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--question-id", required=True)
    parser.add_argument("--question-text", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--duration-sec", type=float, default=0.0)
    parser.add_argument("--asr-provider", default=os.getenv("ASR_PROVIDER", "local_whisper"))
    parser.add_argument("--scoring-provider", default=os.getenv("LLM_PROVIDER", "mock"))
    parser.add_argument("--volume-path", default=os.getenv("DATABRICKS_VOLUME_PATH", DEFAULT_VOLUME_PATH))
    parser.add_argument("--no-databricks", action="store_true", help="Validate only; do not upload or write tables.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    local_audio = Path(args.audio_path).expanduser().resolve()
    real_audio_required = os.getenv("REAL_AUDIO_REQUIRED", "true").strip().lower() in {"1", "true", "yes", "on"}
    guard_real_audio_required(local_audio, real_audio_required=real_audio_required, asr_provider=args.asr_provider)
    metadata = validate_audio_file(local_audio, require_wav_for_real_asr=args.asr_provider != "mock")

    registered_audio_path = str(local_audio)
    if not args.no_databricks:
        registered_audio_path = upload_to_databricks_volume(
            local_audio,
            volume_destination(args.attempt_id, local_audio, args.volume_path),
        )
        ensure_processing_runs_table()

    attempt = Attempt(
        attempt_id=args.attempt_id,
        candidate_id=args.candidate_id,
        question_id=args.question_id,
        question_text=args.question_text,
        audio_path=registered_audio_path,
        audio_format=metadata.audio_format,
        duration_sec=args.duration_sec,
        source="upload",
    )

    run_id = ""
    if not args.no_databricks:
        insert_attempt(attempt)
        run_id = insert_processing_run(
            attempt_id=args.attempt_id,
            audio_path=registered_audio_path,
            audio_sha256=metadata.audio_sha256,
            audio_size_bytes=metadata.audio_size_bytes,
            asr_provider=args.asr_provider,
            asr_is_mock=args.asr_provider == "mock",
            scoring_provider=args.scoring_provider,
            scoring_is_mock=args.scoring_provider == "mock",
            status="REGISTERED",
        )

    print(f"attempt_id={args.attempt_id}")
    print(f"audio_path={registered_audio_path}")
    print(f"audio_sha256={metadata.audio_sha256}")
    print(f"audio_size_bytes={metadata.audio_size_bytes}")
    print(f"asr_provider={args.asr_provider}")
    print(f"scoring_provider={args.scoring_provider}")
    if run_id:
        print(f"processing_run_id={run_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2)
