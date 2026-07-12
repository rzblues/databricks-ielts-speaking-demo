"""Log the latest IELTS demo scoring output to Databricks MLflow tracking."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ielts_scorer.databricks_sql import NAMESPACE, fetch_one, sql_literal
from ielts_scorer.schemas import ScoringReport


def run_cli(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(args, capture_output=True, text=True, check=False, timeout=120)
    if check and completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed


def current_user_name() -> str:
    completed = run_cli(["databricks", "current-user", "me", "-o", "json"])
    return json.loads(completed.stdout).get("userName", "unknown-user")


def experiment_name() -> str:
    return os.getenv("MLFLOW_EXPERIMENT_NAME") or f"/Users/{current_user_name()}/ielts-speaking-demo/ml-platform-enhancement"


def get_or_create_experiment(name: str) -> str:
    completed = run_cli(["databricks", "experiments", "get-by-name", name, "-o", "json"], check=False)
    if completed.returncode == 0:
        data = json.loads(completed.stdout)
        return data.get("experiment_id") or data["experiment"]["experiment_id"]
    created = run_cli(["databricks", "experiments", "create-experiment", name, "-o", "json"])
    return json.loads(created.stdout)["experiment_id"]


def latest_report() -> ScoringReport:
    attempt_id = os.getenv("ATTEMPT_ID", "")
    if not attempt_id:
        raise RuntimeError("ATTEMPT_ID is required so MLflow tracks the same pipeline attempt")
    where = f"WHERE attempt_id = {sql_literal(attempt_id)}"
    row = fetch_one(f"SELECT json_report FROM {NAMESPACE}.scoring_results {where} ORDER BY created_at DESC LIMIT 1")
    if not row:
        raise RuntimeError(f"No scoring_results row found in {NAMESPACE}.scoring_results")
    return ScoringReport.model_validate_json(row[0])


def log_batch(run_id: str, report: ScoringReport) -> None:
    timestamp = int(time.time() * 1000)
    feature = report.features
    metrics = {
        "overall_band": report.overall_band,
        "fc_band": report.fc_band,
        "lr_band": report.lr_band,
        "gra_band": report.gra_band,
        "p_band": report.p_band,
        "confidence": report.confidence,
        "words_per_min": feature.words_per_min,
        "silence_ratio": feature.silence_ratio,
        "lexical_diversity": feature.lexical_diversity,
        "asr_confidence_proxy": feature.asr_confidence_proxy,
    }
    params = {
        "attempt_id": report.attempt_id,
        "model_endpoint": report.model_endpoint,
        "rubric_version": report.rubric_version,
        "asr_provider": report.provenance.asr_provider,
        "scoring_provider": report.provenance.scoring_provider,
        "pipeline_mode": report.provenance.pipeline_mode,
    }
    tags = {
        "demo.area": "ielts-speaking",
        "demo.mlflow_stage": "baseline-tracking",
        "asr_is_mock": str(report.provenance.asr_is_mock).lower(),
        "scoring_is_mock": str(report.provenance.scoring_is_mock).lower(),
    }
    payload: dict[str, Any] = {
        "run_id": run_id,
        "metrics": [{"key": key, "value": float(value), "timestamp": timestamp, "step": 0} for key, value in metrics.items()],
        "params": [{"key": key, "value": str(value)[:250]} for key, value in params.items()],
        "tags": [{"key": key, "value": value[:250]} for key, value in tags.items()],
    }
    run_cli(["databricks", "experiments", "log-batch", "--json", json.dumps(payload)])


def main() -> int:
    name = experiment_name()
    experiment_id = get_or_create_experiment(name)
    report = latest_report()
    run_name = os.getenv("MLFLOW_RUN_NAME", f"ielts-demo-{report.attempt_id}")
    created = run_cli(
        [
            "databricks",
            "experiments",
            "create-run",
            "--experiment-id",
            experiment_id,
            "--run-name",
            run_name,
            "--start-time",
            str(int(time.time() * 1000)),
            "-o",
            "json",
        ]
    )
    run = json.loads(created.stdout)["run"]
    run_id = run["info"]["run_id"]
    log_batch(run_id, report)
    run_cli(
        [
            "databricks",
            "experiments",
            "update-run",
            "--run-id",
            run_id,
            "--status",
            "FINISHED",
            "--end-time",
            str(int(time.time() * 1000)),
        ]
    )

    status = {
        "status": "completed",
        "experiment_name": name,
        "experiment_id": experiment_id,
        "run_id": run_id,
        "attempt_id": report.attempt_id,
        "metrics_logged": [
            "overall_band",
            "fc_band",
            "lr_band",
            "gra_band",
            "p_band",
            "confidence",
            "words_per_min",
            "silence_ratio",
            "lexical_diversity",
            "asr_confidence_proxy",
        ],
    }
    Path("outputs").mkdir(exist_ok=True)
    Path("outputs/mlflow_baseline_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
