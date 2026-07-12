# Databricks notebook source
# MAGIC %pip install -q openai-whisper pydantic>=2.7
# COMMAND ----------

"""Run real Whisper ASR on Databricks compute for one job attempt."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

for base in (Path.cwd(), *Path.cwd().parents):
    if (base / "src" / "ielts_scorer").exists():
        sys.path.insert(0, str(base / "src"))
        break

from ielts_scorer.asr import LocalWhisperASRClient
from ielts_scorer.audio_ingest import validate_attempt_id, validate_audio_file
from ielts_scorer.audio_preprocess import inspect_audio, preprocess_for_asr
from ielts_scorer.schemas import Attempt

dbutils.widgets.text("attempt_id", "attempt_real_final")
dbutils.widgets.text("audio_path", "/Volumes/main/ielts_demo/ielts_audio/attempt_real_final.wav")
dbutils.widgets.text("candidate_id", "demo_candidate_real")
dbutils.widgets.text("question_id", "part2_problem")
dbutils.widgets.text("question_text", "Describe a time you solved a difficult problem.")
dbutils.widgets.text("whisper_model", "/Volumes/main/ielts_demo/ielts_audio/models/tiny.en.pt")

attempt_id = validate_attempt_id(dbutils.widgets.get("attempt_id"))
audio_path = Path(dbutils.widgets.get("audio_path"))
metadata = validate_audio_file(audio_path, require_wav_for_real_asr=True)
processed_audio = preprocess_for_asr(audio_path, Path("/tmp/ielts_scorer_processed"))
duration_sec = inspect_audio(processed_audio).duration_sec
attempt = Attempt(
    attempt_id=attempt_id,
    candidate_id=dbutils.widgets.get("candidate_id"),
    question_id=dbutils.widgets.get("question_id"),
    question_text=dbutils.widgets.get("question_text"),
    audio_path=str(audio_path),
    audio_format=metadata.audio_format,
    duration_sec=duration_sec,
    source="databricks",
)
asr_attempt = attempt.model_copy(update={"audio_path": str(processed_audio)})
segments = [
    segment
    for segment in LocalWhisperASRClient(model_name=dbutils.widgets.get("whisper_model")).transcribe(asr_attempt)
    if segment.text.strip()
]
if not segments:
    raise ValueError("real ASR returned an empty transcript")

attempt_df = spark.createDataFrame([attempt.model_dump()], schema=spark.table("main.ielts_demo.attempts").schema)
segment_df = spark.createDataFrame(
    [segment.model_dump() for segment in segments],
    schema=spark.table("main.ielts_demo.asr_segments").schema,
)
attempt_df.write.mode("overwrite").option("replaceWhere", f"attempt_id = '{attempt_id}'").saveAsTable(
    "main.ielts_demo.attempts"
)
segment_df.write.mode("overwrite").option("replaceWhere", f"attempt_id = '{attempt_id}'").saveAsTable(
    "main.ielts_demo.asr_segments"
)
for table in ("speech_features", "scoring_results"):
    spark.sql(f"DELETE FROM main.ielts_demo.{table} WHERE attempt_id = '{attempt_id}'")

run_id = "run_" + uuid4().hex
processing_record = {
    "run_id": run_id,
    "attempt_id": attempt_id,
    "pipeline_mode": "real_audio",
    "audio_path": str(audio_path),
    "audio_exists": True,
    "audio_sha256": metadata.audio_sha256,
    "audio_size_bytes": metadata.audio_size_bytes,
    "asr_provider": "local_whisper",
    "asr_is_mock": False,
    "scoring_provider": "pending",
    "scoring_is_mock": True,
    "processing_status": "ASR_COMPLETED",
    "error_message": "",
    "created_at": datetime.now(timezone.utc),
}
spark.createDataFrame(
    [processing_record], schema=spark.table("main.ielts_demo.processing_runs").schema
).write.mode("append").saveAsTable("main.ielts_demo.processing_runs")
dbutils.jobs.taskValues.set(key="attempt_id", value=attempt_id)
dbutils.jobs.taskValues.set(key="processing_run_id", value=run_id)
print(f"real ASR completed attempt_id={attempt_id} segments={len(segments)} provider=local_whisper")
