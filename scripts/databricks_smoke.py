"""Databricks smoke check for the IELTS Speaking demo.

This script writes the synthetic sample attempt into Databricks Delta tables
through the SQL Statement API. It uses Databricks CLI auth and does not print
tokens or workspace secrets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ielts_scorer.audio_io import first_attempt, load_segments
from ielts_scorer.databricks_sql import NAMESPACE, run_statement, sql_literal
from ielts_scorer.features import extract_features
from ielts_scorer.scoring import build_mock_report


def insert_row(table: str, columns: list[str], values: list[Any]) -> None:
    column_sql = ", ".join(columns)
    value_sql = ", ".join(sql_literal(value) for value in values)
    run_statement(f"INSERT INTO {NAMESPACE}.{table} ({column_sql}) VALUES ({value_sql})")


def result_count(table: str, attempt_id: str) -> int:
    response = run_statement(f"SELECT COUNT(*) AS count FROM {NAMESPACE}.{table} WHERE attempt_id = {sql_literal(attempt_id)}")
    data = response.get("result", {}).get("data_array", [["0"]])
    return int(data[0][0])


def main() -> int:
    sample_dir = Path("sample_data")
    attempt = first_attempt(sample_dir)
    segments = load_segments(sample_dir / "mock_transcripts.json", attempt.attempt_id)
    features = extract_features(attempt.attempt_id, segments, duration_sec=attempt.duration_sec)
    report = build_mock_report(attempt, segments, features)

    for table in ("attempts", "asr_segments", "speech_features", "scoring_results"):
        run_statement(f"DELETE FROM {NAMESPACE}.{table} WHERE attempt_id = {sql_literal(attempt.attempt_id)}")

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
                segment.attempt_id,
                segment.segment_id,
                segment.start_sec,
                segment.end_sec,
                segment.text,
                segment.avg_logprob,
                segment.no_speech_prob,
                segment.created_at,
            ],
        )

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

    record = report.to_scoring_result_record()
    insert_row("scoring_results", list(record), [record[column] for column in record])

    counts = {table: result_count(table, attempt.attempt_id) for table in ("attempts", "asr_segments", "speech_features", "scoring_results")}
    print(f"namespace={NAMESPACE}")
    print(f"warehouse_id={WAREHOUSE_ID}")
    print(f"attempt_id={attempt.attempt_id}")
    print(f"overall_band={report.overall_band:.1f}")
    for table, count in counts.items():
        print(f"{table}={count}")
    if counts != {"attempts": 1, "asr_segments": len(segments), "speech_features": 1, "scoring_results": 1}:
        raise RuntimeError(f"unexpected Databricks counts: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
