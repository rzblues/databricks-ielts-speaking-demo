# Databricks notebook source

"""Review the final scoring row for the job attempt."""

import re

dbutils.widgets.text("attempt_id", "attempt_real_final")
attempt_id = dbutils.widgets.get("attempt_id")
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", attempt_id):
    raise ValueError("invalid attempt_id")
result = spark.sql(
    f"""
    SELECT attempt_id, overall_band, fc_band, lr_band, gra_band, p_band,
           asr_provider, asr_is_mock, scoring_provider, scoring_is_mock, pipeline_mode, created_at
    FROM main.ielts_demo.scoring_results
    WHERE attempt_id = '{attempt_id}'
    ORDER BY created_at DESC
    LIMIT 1
    """
)
if result.count() != 1:
    raise ValueError(f"no final scoring result for attempt_id={attempt_id}")
display(result)
