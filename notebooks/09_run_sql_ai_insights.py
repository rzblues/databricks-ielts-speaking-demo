# Databricks notebook source

"""Run Databricks SQL AI functions for one transcript."""

import re

dbutils.widgets.text("attempt_id", "attempt_real_final")
attempt_id = dbutils.widgets.get("attempt_id")
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", attempt_id):
    raise ValueError("invalid attempt_id")
spark.sql(f"DELETE FROM main.ielts_demo.ai_function_insights WHERE attempt_id = '{attempt_id}'")
spark.sql(
    f"""
    INSERT INTO main.ielts_demo.ai_function_insights
    WITH transcript AS (
      SELECT concat_ws(' ', transform(sort_array(collect_list(named_struct('segment_id', segment_id, 'text', text))), x -> x.text)) AS text
      FROM main.ielts_demo.asr_segments
      WHERE attempt_id = '{attempt_id}'
    )
    SELECT current_timestamp(), '{attempt_id}', ai_analyze_sentiment(text),
           ai_classify(text, array('fluent', 'hesitant', 'off_topic', 'underdeveloped')),
           substr(text, 1, 500), 'databricks_sql_ai_functions', false, 'Job-scoped SQL AI enrichment'
    FROM transcript
    WHERE text IS NOT NULL AND trim(text) <> ''
    """
)
row = spark.sql(
    f"SELECT sentiment, delivery_label FROM main.ielts_demo.ai_function_insights WHERE attempt_id = '{attempt_id}'"
).first()
if row is None:
    raise RuntimeError(f"SQL AI did not produce an insight for attempt_id={attempt_id}")
print(f"SQL AI completed attempt_id={attempt_id} sentiment={row['sentiment']} delivery={row['delivery_label']}")
