"""Score the latest Databricks attempt with a Databricks Model Serving endpoint."""

from __future__ import annotations

import json
import os
import sys
from uuid import uuid4
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ielts_scorer.databricks_sql import NAMESPACE, fetch_data_array, fetch_one, run_statement, sql_literal
from ielts_scorer.model_serving import build_model_serving_report, invoke_chat_endpoint, model_serving_prompt
from ielts_scorer.provider_provenance import ProviderProvenance
from ielts_scorer.scoring import build_mock_report
from ielts_scorer.schemas import ASRSegment, Attempt, SpeechFeatures


def table_columns(table: str) -> list[str]:
    if table == "attempts":
        return [
            "attempt_id",
            "candidate_id",
            "question_id",
            "question_text",
            "audio_path",
            "audio_format",
            "duration_sec",
            "source",
            "created_at",
        ]
    if table == "asr_segments":
        return ["attempt_id", "segment_id", "start_sec", "end_sec", "text", "avg_logprob", "no_speech_prob", "created_at"]
    if table == "speech_features":
        return [
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
        ]
    raise ValueError(f"unknown table {table}")


def row_dict(table: str, row: list[object]) -> dict[str, object]:
    return dict(zip(table_columns(table), row))


def sql_boolean(value: object) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise ValueError(f"unsupported SQL boolean value: {value!r}")


def load_attempt_bundle(attempt_id: str | None) -> tuple[Attempt, list[ASRSegment], SpeechFeatures, ProviderProvenance, str]:
    where = f"WHERE attempt_id = {sql_literal(attempt_id)}" if attempt_id else ""
    attempt_row = fetch_one(f"SELECT {', '.join(table_columns('attempts'))} FROM {NAMESPACE}.attempts {where} ORDER BY created_at DESC LIMIT 1")
    if not attempt_row:
        raise RuntimeError(f"No attempt row found in {NAMESPACE}.attempts")
    attempt = Attempt.model_validate(row_dict("attempts", attempt_row))
    segment_rows = fetch_data_array(
        f"SELECT {', '.join(table_columns('asr_segments'))} FROM {NAMESPACE}.asr_segments "
        f"WHERE attempt_id = {sql_literal(attempt.attempt_id)} ORDER BY segment_id"
    )
    if not segment_rows:
        raise RuntimeError(f"No ASR segments found for attempt_id={attempt.attempt_id}")
    segments = [ASRSegment.model_validate(row_dict("asr_segments", row)) for row in segment_rows]
    feature_row = fetch_one(
        f"SELECT {', '.join(table_columns('speech_features'))} FROM {NAMESPACE}.speech_features "
        f"WHERE attempt_id = {sql_literal(attempt.attempt_id)} ORDER BY created_at DESC LIMIT 1"
    )
    if not feature_row:
        raise RuntimeError(f"No speech_features row found for attempt_id={attempt.attempt_id}")
    features = SpeechFeatures.model_validate(row_dict("speech_features", feature_row))
    processing_row = fetch_one(
        f"""
        SELECT run_id, pipeline_mode, asr_provider, asr_is_mock
        FROM {NAMESPACE}.processing_runs
        WHERE attempt_id = {sql_literal(attempt.attempt_id)}
          AND asr_provider IS NOT NULL
          AND asr_provider <> 'pending'
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    if not processing_row:
        raise RuntimeError(f"No completed ASR provenance found for attempt_id={attempt.attempt_id}")
    run_id, pipeline_mode, asr_provider, asr_is_mock = processing_row
    provenance = ProviderProvenance(
        audio_source="real_audio" if pipeline_mode == "real_audio" else "mock",
        asr_provider=str(asr_provider),
        asr_is_mock=sql_boolean(asr_is_mock),
        scoring_provider="pending",
        scoring_is_mock=True,
        pipeline_mode=str(pipeline_mode),
    )
    return attempt, segments, features, provenance, str(run_id)


def insert_scoring_report(report) -> None:
    record = report.to_scoring_result_record()
    columns = list(record)
    values = ", ".join(sql_literal(record[column]) for column in columns)
    run_statement(f"INSERT INTO {NAMESPACE}.scoring_results ({', '.join(columns)}) VALUES ({values})")


def score_with_repair(attempt, segments, features, endpoint, provenance):
    messages = model_serving_prompt(attempt, segments, features)
    payload = invoke_chat_endpoint(endpoint, messages, max_tokens=2000)
    try:
        return build_model_serving_report(attempt, segments, features, endpoint, payload, provenance), None
    except Exception as first_error:
        messages.extend(
            [
                {"role": "assistant", "content": json.dumps(payload, ensure_ascii=True)[:12000]},
                {
                    "role": "user",
                    "content": "The previous response failed schema validation. Return only one corrected JSON object matching the requested schema.",
                },
            ]
        )
        repaired_payload = invoke_chat_endpoint(endpoint, messages, max_tokens=2000)
        try:
            return build_model_serving_report(attempt, segments, features, endpoint, repaired_payload, provenance), str(first_error)
        except Exception as second_error:
            required = os.getenv("REAL_LLM_REQUIRED", "true").lower() in {"1", "true", "yes", "on"}
            if required:
                raise RuntimeError(f"Model response failed validation after one repair: {second_error}") from second_error
            fallback_provenance = ProviderProvenance.model_validate(
                {
                    **provenance.model_dump(),
                    "scoring_provider": "rule_based_mock",
                    "scoring_is_mock": True,
                }
            )
            return build_mock_report(attempt, segments, features, provenance=fallback_provenance), str(second_error)


def main() -> int:
    endpoint = os.getenv("DATABRICKS_MODEL_ENDPOINT", "databricks-gpt-oss-20b")
    requested_attempt_id = os.getenv("ATTEMPT_ID")
    if not requested_attempt_id:
        raise RuntimeError("ATTEMPT_ID is required so Model Serving scores the same pipeline attempt")
    attempt, segments, features, provenance, processing_run_id = load_attempt_bundle(requested_attempt_id)
    report, repair_error = score_with_repair(attempt, segments, features, endpoint, provenance)
    insert_scoring_report(report)
    run_statement(
        f"""
        UPDATE {NAMESPACE}.processing_runs
        SET scoring_provider = {sql_literal(report.provenance.scoring_provider)},
            scoring_is_mock = {sql_literal(report.provenance.scoring_is_mock)},
            processing_status = 'COMPLETED',
            error_message = {sql_literal(repair_error or '')}
        WHERE run_id = {sql_literal(processing_run_id)}
        """
    )
    status = {
        "status": "completed",
        "attempt_id": report.attempt_id,
        "endpoint": endpoint,
        "overall_band": report.overall_band,
        "scoring_provider": report.provenance.scoring_provider,
        "scoring_is_mock": report.provenance.scoring_is_mock,
        "processing_run_id": processing_run_id,
        "repair_attempted": repair_error is not None,
    }
    Path("outputs").mkdir(exist_ok=True)
    Path("outputs/model_serving_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
