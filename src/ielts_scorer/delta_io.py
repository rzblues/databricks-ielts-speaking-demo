"""Delta table contracts and local fallback storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

TABLE_COLUMNS = {
    "attempts": [
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
    "asr_segments": [
        "attempt_id",
        "segment_id",
        "start_sec",
        "end_sec",
        "text",
        "avg_logprob",
        "no_speech_prob",
        "created_at",
    ],
    "speech_features": [
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
    "scoring_results": [
        "attempt_id",
        "overall_band",
        "fc_band",
        "lr_band",
        "gra_band",
        "p_band",
        "confidence",
        "json_report",
        "model_endpoint",
        "rubric_version",
        "audio_source",
        "asr_provider",
        "asr_is_mock",
        "scoring_provider",
        "scoring_is_mock",
        "pipeline_mode",
        "created_at",
    ],
    "processing_runs": [
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
}


def validate_table_record(table_name: str, record: dict[str, Any]) -> None:
    expected = set(TABLE_COLUMNS[table_name])
    missing = expected - set(record)
    if missing:
        raise ValueError(f"{table_name} record missing columns: {sorted(missing)}")


class LocalDeltaStore:
    """JSONL fallback that mirrors the table names used in Databricks."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, table_name: str) -> Path:
        if table_name not in TABLE_COLUMNS:
            raise ValueError(f"unknown table: {table_name}")
        return self.root / f"{table_name}.jsonl"

    def write_records(self, table_name: str, records: Iterable[dict[str, Any]]) -> Path:
        path = self.path_for(table_name)
        with path.open("a", encoding="utf-8") as handle:
            for record in records:
                validate_table_record(table_name, record)
                handle.write(json.dumps(record, default=str, sort_keys=True) + "\n")
        return path

    def read_records(self, table_name: str) -> list[dict[str, Any]]:
        path = self.path_for(table_name)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def create_spark_table_if_needed(spark: Any, namespace: str, table_name: str) -> None:
    columns = ", ".join(f"{column} STRING" for column in TABLE_COLUMNS[table_name])
    spark.sql(f"CREATE TABLE IF NOT EXISTS {namespace}.{table_name} ({columns}) USING DELTA")
