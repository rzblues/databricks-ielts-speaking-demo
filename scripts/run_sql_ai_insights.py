"""Use Databricks SQL AI functions for auxiliary transcript insights."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ielts_scorer.databricks_sql import NAMESPACE, fetch_one, run_statement, sql_literal

INSIGHTS_TABLE = f"{NAMESPACE}.ai_function_insights"


def main() -> int:
    attempt_id = os.getenv("ATTEMPT_ID", "")
    if not attempt_id:
        raise RuntimeError("ATTEMPT_ID is required so SQL AI enriches the same pipeline attempt")
    attempt_filter = f"WHERE attempt_id = {sql_literal(attempt_id)}"
    run_statement(f"DELETE FROM {INSIGHTS_TABLE} WHERE attempt_id = {sql_literal(attempt_id)}")
    run_statement(
        f"""
        CREATE TABLE IF NOT EXISTS {INSIGHTS_TABLE} (
          created_at TIMESTAMP,
          attempt_id STRING,
          sentiment STRING,
          delivery_label STRING,
          transcript_preview STRING,
          provider STRING,
          is_mock BOOLEAN,
          notes STRING
        ) USING DELTA
        """
    )
    run_statement(
        f"""
        INSERT INTO {INSIGHTS_TABLE}
        WITH transcripts AS (
          SELECT
            attempt_id,
            concat_ws(' ', transform(sort_array(collect_list(named_struct('segment_id', segment_id, 'text', text))), x -> x.text)) AS transcript
          FROM {NAMESPACE}.asr_segments
          {attempt_filter}
          GROUP BY attempt_id
        )
        SELECT
          current_timestamp(),
          attempt_id,
          ai_analyze_sentiment(transcript) AS sentiment,
          ai_classify(transcript, array('fluent', 'hesitant', 'off_topic', 'underdeveloped')) AS delivery_label,
          substr(transcript, 1, 500) AS transcript_preview,
          'databricks_sql_ai_functions' AS provider,
          false AS is_mock,
          'M5 SQL AI function enrichment' AS notes
        FROM transcripts
        """
    )
    count_row = fetch_one(f"SELECT COUNT(*) FROM {INSIGHTS_TABLE} {attempt_filter}")
    latest_row = fetch_one(
        f"""
        SELECT attempt_id, sentiment, delivery_label
        FROM {INSIGHTS_TABLE}
        {attempt_filter}
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    output = {
        "status": "completed",
        "insights_table": INSIGHTS_TABLE,
        "rows_for_filter": int(count_row[0]) if count_row else 0,
        "latest": {
            "attempt_id": latest_row[0],
            "sentiment": latest_row[1],
            "delivery_label": latest_row[2],
        }
        if latest_row
        else None,
    }
    Path("outputs").mkdir(exist_ok=True)
    Path("outputs/sql_ai_insights_status.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    if not latest_row:
        raise RuntimeError("SQL AI insight table did not receive any rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
