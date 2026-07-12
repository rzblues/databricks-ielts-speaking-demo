# Databricks notebook source

"""Explicit rule-based fallback scorer for one Delta attempt."""

import sys
from pathlib import Path

for base in (Path.cwd(), *Path.cwd().parents):
    if (base / "src" / "ielts_scorer").exists():
        sys.path.insert(0, str(base / "src"))
        break

from ielts_scorer.provider_provenance import ProviderProvenance
from ielts_scorer.audio_ingest import validate_attempt_id
from ielts_scorer.scoring import build_mock_report
from ielts_scorer.schemas import ASRSegment, Attempt, SpeechFeatures

dbutils.widgets.text("attempt_id", "attempt_real_final")
dbutils.widgets.dropdown("mock_llm", "false", ["false", "true"])
if dbutils.widgets.get("mock_llm") != "true":
    raise ValueError("This notebook is fallback-only. Use 10_score_with_model_serving.py for the real scoring path.")

attempt_id = validate_attempt_id(dbutils.widgets.get("attempt_id"))
attempt = Attempt.model_validate(
    spark.sql(f"SELECT * FROM main.ielts_demo.attempts WHERE attempt_id = '{attempt_id}' ORDER BY created_at DESC LIMIT 1").first().asDict()
)
segments = [
    ASRSegment.model_validate(row.asDict())
    for row in spark.sql(f"SELECT * FROM main.ielts_demo.asr_segments WHERE attempt_id = '{attempt_id}' ORDER BY segment_id").collect()
]
features = SpeechFeatures.model_validate(
    spark.sql(f"SELECT * FROM main.ielts_demo.speech_features WHERE attempt_id = '{attempt_id}' ORDER BY created_at DESC LIMIT 1").first().asDict()
)
asr_row = spark.sql(
    f"SELECT pipeline_mode, asr_provider, asr_is_mock FROM main.ielts_demo.processing_runs "
    f"WHERE attempt_id = '{attempt_id}' ORDER BY created_at DESC LIMIT 1"
).first()
provenance = ProviderProvenance(
    audio_source="real_audio" if asr_row["pipeline_mode"] == "real_audio" else "mock",
    asr_provider=asr_row["asr_provider"],
    asr_is_mock=asr_row["asr_is_mock"],
    scoring_provider="rule_based_mock",
    scoring_is_mock=True,
    pipeline_mode=asr_row["pipeline_mode"],
)
report = build_mock_report(attempt, segments, features, provenance=provenance)
record = report.to_scoring_result_record()
spark.createDataFrame([record], schema=spark.table("main.ielts_demo.scoring_results").schema).write.mode(
    "overwrite"
).option("replaceWhere", f"attempt_id = '{attempt_id}'").saveAsTable("main.ielts_demo.scoring_results")
print(f"fallback scoring completed attempt_id={attempt_id} scoring_is_mock=true")
