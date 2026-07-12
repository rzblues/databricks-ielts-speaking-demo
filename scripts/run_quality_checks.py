"""Run demo data quality checks and optionally create a Lakehouse monitor."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ielts_scorer.databricks_sql import NAMESPACE, WAREHOUSE_ID, fetch_one, run_statement, sql_literal

RESULTS_TABLE = f"{NAMESPACE}.quality_check_results"


CHECKS = {
    "attempts_have_audio_paths": f"SELECT COUNT(*) FROM {NAMESPACE}.attempts WHERE audio_path IS NULL OR audio_path = ''",
    "segments_have_text": f"SELECT COUNT(*) FROM {NAMESPACE}.asr_segments WHERE text IS NULL OR trim(text) = ''",
    "features_in_valid_ranges": f"""
        SELECT COUNT(*) FROM {NAMESPACE}.speech_features
        WHERE silence_ratio < 0 OR silence_ratio > 1
           OR lexical_diversity < 0 OR lexical_diversity > 1
           OR asr_confidence_proxy < 0 OR asr_confidence_proxy > 1
           OR words_per_min < 0
    """,
    "scores_in_valid_ranges": f"""
        SELECT COUNT(*) FROM {NAMESPACE}.scoring_results
        WHERE overall_band < 0 OR overall_band > 9
           OR fc_band < 0 OR fc_band > 9
           OR lr_band < 0 OR lr_band > 9
           OR gra_band < 0 OR gra_band > 9
           OR p_band < 0 OR p_band > 9
    """,
    "overall_matches_dimension_average": f"""
        SELECT COUNT(*) FROM {NAMESPACE}.scoring_results
        WHERE overall_band <> round((fc_band + lr_band + gra_band + p_band) / 4.0 * 2) / 2
    """,
    "scoring_rows_have_provenance": f"""
        SELECT COUNT(*) FROM {NAMESPACE}.scoring_results
        WHERE audio_source IS NULL OR asr_provider IS NULL OR asr_is_mock IS NULL
           OR scoring_provider IS NULL OR scoring_is_mock IS NULL OR pipeline_mode IS NULL
    """,
    "real_audio_rows_do_not_use_mock_asr": f"""
        SELECT COUNT(*) FROM {NAMESPACE}.scoring_results
        WHERE pipeline_mode = 'real_audio' AND (audio_source <> 'real_audio' OR asr_is_mock = true)
    """,
    "scoring_rows_join_attempts": f"""
        SELECT COUNT(*) FROM {NAMESPACE}.scoring_results sr
        LEFT JOIN {NAMESPACE}.attempts a ON sr.attempt_id = a.attempt_id
        WHERE a.attempt_id IS NULL
    """,
}


def create_results_table() -> None:
    run_statement(
        f"""
        CREATE TABLE IF NOT EXISTS {RESULTS_TABLE} (
          check_time TIMESTAMP,
          check_name STRING,
          status STRING,
          failing_rows BIGINT,
          expectation_sql STRING,
          notes STRING
        ) USING DELTA
        """
    )


def run_checks() -> list[dict[str, object]]:
    create_results_table()
    results = []
    for name, query in CHECKS.items():
        row = fetch_one(query)
        failing_rows = int(row[0]) if row else 0
        status = "PASS" if failing_rows == 0 else "FAIL"
        run_statement(
            f"""
            INSERT INTO {RESULTS_TABLE}
            (check_time, check_name, status, failing_rows, expectation_sql, notes)
            VALUES (current_timestamp(), {sql_literal(name)}, {sql_literal(status)}, {failing_rows},
                    {sql_literal(' '.join(query.split()))}, {sql_literal('M4 platform quality check')})
            """
        )
        results.append({"check_name": name, "status": status, "failing_rows": failing_rows})
    return results


def current_user_name() -> str:
    completed = subprocess.run(["databricks", "current-user", "me", "-o", "json"], capture_output=True, text=True, check=False, timeout=60)
    if completed.returncode != 0:
        return "unknown-user"
    return json.loads(completed.stdout).get("userName", "unknown-user")


def ensure_lakehouse_monitor() -> dict[str, object]:
    user = current_user_name()
    assets_dir = f"/Workspace/Users/{user}/ielts-speaking-demo/monitoring"
    completed = subprocess.run(
        [
            "databricks",
            "quality-monitors",
            "create",
            f"{NAMESPACE}.speech_features",
            "--warehouse-id",
            WAREHOUSE_ID,
            "--json",
            json.dumps({"output_schema_name": NAMESPACE, "assets_dir": assets_dir, "snapshot": {}}),
            "-o",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if completed.returncode == 0:
        return {"status": "created", "table": f"{NAMESPACE}.speech_features", "assets_dir": assets_dir}
    message = completed.stderr.strip() or completed.stdout.strip()
    if "already" in message.lower() or "exists" in message.lower():
        return {"status": "already_exists", "table": f"{NAMESPACE}.speech_features", "assets_dir": assets_dir}
    return {"status": "warning", "table": f"{NAMESPACE}.speech_features", "assets_dir": assets_dir, "message": message[:1000]}


def main() -> int:
    results = run_checks()
    monitor = ensure_lakehouse_monitor()
    failed = [result for result in results if result["status"] != "PASS"]
    output = {
        "status": "completed" if not failed else "failed",
        "results_table": RESULTS_TABLE,
        "checks": results,
        "lakehouse_monitor": monitor,
    }
    Path("outputs").mkdir(exist_ok=True)
    Path("outputs/quality_checks_status.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    if failed:
        raise RuntimeError(f"Quality checks failed: {failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
