# Databricks notebook source

"""Register one real audio path in the Delta attempts table."""

import sys
from pathlib import Path

for base in (Path.cwd(), *Path.cwd().parents):
    if (base / "src" / "ielts_scorer").exists():
        sys.path.insert(0, str(base / "src"))
        break

from ielts_scorer.audio_ingest import validate_attempt_id, validate_audio_file
from ielts_scorer.audio_preprocess import inspect_audio
from ielts_scorer.schemas import Attempt

dbutils.widgets.text("attempt_id", "attempt_real_final")
dbutils.widgets.text("audio_path", "/Volumes/main/ielts_demo/ielts_audio/attempt_real_final.wav")
dbutils.widgets.text("candidate_id", "demo_candidate_real")
dbutils.widgets.text("question_id", "part2_problem")
dbutils.widgets.text("question_text", "Describe a time you solved a difficult problem.")

attempt_id = validate_attempt_id(dbutils.widgets.get("attempt_id"))
audio_path = Path(dbutils.widgets.get("audio_path"))
metadata = validate_audio_file(audio_path, require_wav_for_real_asr=True)
inspection = inspect_audio(audio_path)
attempt = Attempt(
    attempt_id=attempt_id,
    candidate_id=dbutils.widgets.get("candidate_id"),
    question_id=dbutils.widgets.get("question_id"),
    question_text=dbutils.widgets.get("question_text"),
    audio_path=str(audio_path),
    audio_format=metadata.audio_format,
    duration_sec=inspection.duration_sec,
    source="databricks",
)

spark.createDataFrame([attempt.model_dump()], schema=spark.table("main.ielts_demo.attempts").schema).write.mode(
    "overwrite"
).option("replaceWhere", f"attempt_id = '{attempt_id}'").saveAsTable("main.ielts_demo.attempts")
dbutils.jobs.taskValues.set(key="attempt_id", value=attempt_id)
print(f"registered real audio attempt_id={attempt_id} path={audio_path}")
