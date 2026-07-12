# Databricks notebook source

"""Track the model-scored attempt with native Databricks MLflow."""

import sys
from pathlib import Path

for base in (Path.cwd(), *Path.cwd().parents):
    if (base / "src" / "ielts_scorer").exists():
        sys.path.insert(0, str(base / "src"))
        break

import mlflow

from ielts_scorer.audio_ingest import validate_attempt_id
from ielts_scorer.schemas import ScoringReport

dbutils.widgets.text("attempt_id", "attempt_real_final")
attempt_id = validate_attempt_id(dbutils.widgets.get("attempt_id"))
row = spark.sql(
    f"SELECT json_report FROM main.ielts_demo.scoring_results WHERE attempt_id = '{attempt_id}' ORDER BY created_at DESC LIMIT 1"
).first()
if row is None:
    raise ValueError(f"no scoring report for attempt_id={attempt_id}")
report = ScoringReport.model_validate_json(row["json_report"])
user_name = spark.sql("SELECT current_user()").first()[0]
experiment_name = f"/Users/{user_name}/ielts-speaking-demo/ml-platform-enhancement"
mlflow.set_experiment(experiment_name)

with mlflow.start_run(run_name=f"ielts-demo-{attempt_id}") as run:
    mlflow.log_metrics(
        {
            "overall_band": report.overall_band,
            "fc_band": report.fc_band,
            "lr_band": report.lr_band,
            "gra_band": report.gra_band,
            "p_band": report.p_band,
            "confidence": report.confidence,
            "words_per_min": report.features.words_per_min,
            "silence_ratio": report.features.silence_ratio,
            "lexical_diversity": report.features.lexical_diversity,
            "asr_confidence_proxy": report.features.asr_confidence_proxy,
        }
    )
    mlflow.log_params(
        {
            "attempt_id": report.attempt_id,
            "model_endpoint": report.model_endpoint,
            "rubric_version": report.rubric_version,
            "asr_provider": report.provenance.asr_provider,
            "scoring_provider": report.provenance.scoring_provider,
            "pipeline_mode": report.provenance.pipeline_mode,
        }
    )
    mlflow.set_tags(
        {
            "demo.area": "ielts-speaking",
            "asr_is_mock": str(report.provenance.asr_is_mock).lower(),
            "scoring_is_mock": str(report.provenance.scoring_is_mock).lower(),
        }
    )
    mlflow.log_text(report.model_dump_json(indent=2), "scoring_report.json")
    run_id = run.info.run_id

dbutils.jobs.taskValues.set(key="mlflow_run_id", value=run_id)
print(f"MLflow run finished run_id={run_id} attempt_id={attempt_id}")
