"""Publish a Delta feature mirror when Feature Engineering compute is unavailable.

The real Feature Engineering path is notebooks/07_publish_feature_table.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ielts_scorer.databricks_sql import NAMESPACE, fetch_one, run_statement, sql_literal

FEATURE_TABLE = f"{NAMESPACE}.speech_feature_table"
LIFECYCLE_TABLE = f"{NAMESPACE}.feature_lifecycle_events"


def has_feature_engineering_sdk() -> bool:
    try:
        __import__("databricks.feature_engineering")
        return True
    except Exception:
        return False


def main() -> int:
    run_statement(
        f"""
        CREATE TABLE IF NOT EXISTS {LIFECYCLE_TABLE} (
          event_time TIMESTAMP,
          feature_table STRING,
          attempt_id STRING,
          feature_version STRING,
          source_table STRING,
          sdk_available BOOLEAN,
          quality_status STRING,
          notes STRING
        ) USING DELTA
        """
    )
    run_statement(
        f"""
        CREATE OR REPLACE TABLE {FEATURE_TABLE}
        AS
        SELECT
          attempt_id,
          duration_sec,
          speaking_sec,
          silence_ratio,
          words_count,
          words_per_min,
          pause_count,
          long_pause_count,
          avg_pause_sec,
          filler_count,
          filler_ratio,
          repetition_count,
          lexical_diversity,
          avg_sentence_len,
          complex_sentence_proxy,
          asr_confidence_proxy,
          created_at AS feature_timestamp,
          'main.ielts_demo.speech_features' AS source_table,
          'speech-features-v1' AS feature_version
        FROM {NAMESPACE}.speech_features
        """
    )
    row = fetch_one(f"SELECT COUNT(*), COUNT(DISTINCT attempt_id) FROM {FEATURE_TABLE}")
    count = int(row[0]) if row else 0
    distinct_attempts = int(row[1]) if row else 0
    sdk_available = has_feature_engineering_sdk()
    status = "PASS" if count > 0 and distinct_attempts > 0 else "FAIL"
    run_statement(
        f"""
        INSERT INTO {LIFECYCLE_TABLE}
        (event_time, feature_table, attempt_id, feature_version, source_table, sdk_available, quality_status, notes)
        SELECT current_timestamp(), {sql_literal(FEATURE_TABLE)}, attempt_id, 'speech-features-v1',
               {sql_literal(f'{NAMESPACE}.speech_features')}, {sql_literal(sdk_available)}, {sql_literal(status)},
               {sql_literal('Delta mirror only; run notebook 07 for Feature Engineering registration')}
        FROM {FEATURE_TABLE}
        """
    )
    output = {
        "status": "completed" if status == "PASS" else "failed",
        "feature_table": FEATURE_TABLE,
        "feature_version": "speech-features-v1",
        "rows": count,
        "distinct_attempts": distinct_attempts,
        "feature_engineering_sdk_available": sdk_available,
        "registration_mode": "delta_mirror_not_feature_store",
    }
    Path("outputs").mkdir(exist_ok=True)
    Path("outputs/feature_table_status.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    if status != "PASS":
        raise RuntimeError(f"Feature table publish failed quality gate: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
