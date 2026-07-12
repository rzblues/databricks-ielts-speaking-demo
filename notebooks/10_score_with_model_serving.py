# Databricks notebook source

"""Score one Delta attempt with a live Databricks Model Serving endpoint."""

import json
import sys
from pathlib import Path

for base in (Path.cwd(), *Path.cwd().parents):
    if (base / "src" / "ielts_scorer").exists():
        sys.path.insert(0, str(base / "src"))
        break

from ielts_scorer.model_serving import build_model_serving_report, invoke_chat_endpoint, model_serving_prompt
from ielts_scorer.audio_ingest import validate_attempt_id
from ielts_scorer.provider_provenance import ProviderProvenance
from ielts_scorer.scoring import build_mock_report
from ielts_scorer.schemas import ASRSegment, Attempt, SpeechFeatures

dbutils.widgets.text("attempt_id", "attempt_real_final")
dbutils.widgets.text("model_endpoint", "databricks-gpt-oss-20b")
dbutils.widgets.dropdown("real_llm_required", "true", ["true", "false"])
attempt_id = validate_attempt_id(dbutils.widgets.get("attempt_id"))
endpoint = dbutils.widgets.get("model_endpoint")

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
processing = spark.sql(
    f"SELECT run_id, pipeline_mode, asr_provider, asr_is_mock FROM main.ielts_demo.processing_runs "
    f"WHERE attempt_id = '{attempt_id}' AND asr_provider <> 'pending' ORDER BY created_at DESC LIMIT 1"
).first()
if processing is None:
    raise ValueError(f"missing ASR provenance for attempt_id={attempt_id}")
provenance = ProviderProvenance(
    audio_source="real_audio" if processing["pipeline_mode"] == "real_audio" else "mock",
    asr_provider=processing["asr_provider"],
    asr_is_mock=processing["asr_is_mock"],
    scoring_provider="pending",
    scoring_is_mock=True,
    pipeline_mode=processing["pipeline_mode"],
)

messages = model_serving_prompt(attempt, segments, features)
payload = invoke_chat_endpoint(endpoint, messages, max_tokens=2000)
repair_error = ""
try:
    report = build_model_serving_report(attempt, segments, features, endpoint, payload, provenance)
except Exception as first_error:
    repair_error = str(first_error)
    messages.extend(
        [
            {"role": "assistant", "content": json.dumps(payload, ensure_ascii=True)[:12000]},
            {"role": "user", "content": "Return only one corrected JSON object matching the requested schema."},
        ]
    )
    repaired = invoke_chat_endpoint(endpoint, messages, max_tokens=2000)
    try:
        report = build_model_serving_report(attempt, segments, features, endpoint, repaired, provenance)
    except Exception:
        if dbutils.widgets.get("real_llm_required") == "true":
            raise
        fallback = ProviderProvenance.model_validate(
            {**provenance.model_dump(), "scoring_provider": "rule_based_mock", "scoring_is_mock": True}
        )
        report = build_mock_report(attempt, segments, features, provenance=fallback)

record = report.to_scoring_result_record()
spark.createDataFrame([record], schema=spark.table("main.ielts_demo.scoring_results").schema).write.mode(
    "overwrite"
).option("replaceWhere", f"attempt_id = '{attempt_id}'").saveAsTable("main.ielts_demo.scoring_results")
repair_error_sql = repair_error.replace("'", "''")
scoring_provider_sql = report.provenance.scoring_provider.replace("'", "''")
spark.sql(
    f"""
    UPDATE main.ielts_demo.processing_runs
    SET scoring_provider = '{scoring_provider_sql}',
        scoring_is_mock = {str(report.provenance.scoring_is_mock).lower()},
        processing_status = 'COMPLETED',
        error_message = '{repair_error_sql}'
    WHERE run_id = '{processing['run_id']}'
    """
)
if report.provenance.scoring_is_mock and dbutils.widgets.get("real_llm_required") == "true":
    raise RuntimeError("real_llm_required=true but scoring fell back to mock")
print(f"Model Serving completed attempt_id={attempt_id} provider={report.provenance.scoring_provider}")
