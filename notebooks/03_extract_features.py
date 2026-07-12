# Databricks notebook source

"""Extract features from the Delta ASR segments for one attempt."""

import sys
from pathlib import Path

for base in (Path.cwd(), *Path.cwd().parents):
    if (base / "src" / "ielts_scorer").exists():
        sys.path.insert(0, str(base / "src"))
        break

from ielts_scorer.features import extract_features
from ielts_scorer.audio_ingest import validate_attempt_id
from ielts_scorer.schemas import ASRSegment

dbutils.widgets.text("attempt_id", "attempt_real_final")
attempt_id = validate_attempt_id(dbutils.widgets.get("attempt_id"))
attempt_rows = spark.sql(
    f"SELECT duration_sec FROM main.ielts_demo.attempts WHERE attempt_id = '{attempt_id}' ORDER BY created_at DESC LIMIT 1"
).collect()
segment_rows = spark.sql(
    f"SELECT * FROM main.ielts_demo.asr_segments WHERE attempt_id = '{attempt_id}' ORDER BY segment_id"
).collect()
if not attempt_rows or not segment_rows:
    raise ValueError(f"attempt or ASR segments missing for attempt_id={attempt_id}")

segments = [ASRSegment.model_validate(row.asDict()) for row in segment_rows]
features = extract_features(attempt_id, segments, duration_sec=float(attempt_rows[0]["duration_sec"]))
spark.createDataFrame(
    [features.model_dump()], schema=spark.table("main.ielts_demo.speech_features").schema
).write.mode("overwrite").option("replaceWhere", f"attempt_id = '{attempt_id}'").saveAsTable(
    "main.ielts_demo.speech_features"
)
print(f"features completed attempt_id={attempt_id} words={features.words_count}")
