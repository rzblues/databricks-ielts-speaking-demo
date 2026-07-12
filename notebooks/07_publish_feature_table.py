# Databricks notebook source
# MAGIC %pip install -q databricks-feature-engineering
# COMMAND ----------

"""Publish speech features through the Databricks Feature Engineering client."""

from datetime import datetime, timezone

from databricks.feature_engineering import FeatureEngineeringClient
from pyspark.sql import functions as F

dbutils.widgets.text("attempt_id", "attempt_real_final")
attempt_id = dbutils.widgets.get("attempt_id")
feature_table = "main.ielts_demo.speech_feature_table"
source = spark.table("main.ielts_demo.speech_features").where(F.col("attempt_id") == attempt_id)
if source.count() != 1:
    raise ValueError(f"expected one speech_features row for attempt_id={attempt_id}")
feature_df = source.select(
    "attempt_id",
    "duration_sec",
    "speaking_sec",
    "silence_ratio",
    "words_count",
    "words_per_min",
    "pause_count",
    "long_pause_count",
    "avg_pause_sec",
    "filler_count",
    "filler_ratio",
    "repetition_count",
    "lexical_diversity",
    "avg_sentence_len",
    "complex_sentence_proxy",
    "asr_confidence_proxy",
    F.col("created_at").alias("feature_timestamp"),
    F.lit("main.ielts_demo.speech_features").alias("source_table"),
    F.lit("speech-features-v1").alias("feature_version"),
)

client = FeatureEngineeringClient()
table_metadata = None
try:
    table_metadata = client.get_table(name=feature_table)
except Exception:
    if spark.catalog.tableExists(feature_table):
        spark.sql(f"DROP TABLE {feature_table}")

primary_keys = list(getattr(table_metadata, "primary_keys", []) or []) if table_metadata else []
if table_metadata is not None and primary_keys != ["attempt_id"]:
    spark.sql(f"DROP TABLE {feature_table}")
    table_metadata = None

if table_metadata is None:
    client.create_table(
        name=feature_table,
        primary_keys=["attempt_id"],
        df=feature_df,
        description="IELTS demo speech features keyed by attempt_id.",
    )
else:
    client.write_table(name=feature_table, df=feature_df, mode="merge")

verified_metadata = client.get_table(name=feature_table)
verified_keys = list(getattr(verified_metadata, "primary_keys", []) or [])
if verified_keys != ["attempt_id"]:
    raise RuntimeError(f"Feature Engineering registration did not expose attempt_id as primary key: {verified_keys}")

lifecycle = {
    "event_time": datetime.now(timezone.utc),
    "feature_table": feature_table,
    "attempt_id": attempt_id,
    "feature_version": "speech-features-v1",
    "source_table": "main.ielts_demo.speech_features",
    "sdk_available": True,
    "quality_status": "PASS",
    "notes": "Registered and merged through Databricks FeatureEngineeringClient",
}
spark.createDataFrame(
    [lifecycle], schema=spark.table("main.ielts_demo.feature_lifecycle_events").schema
).write.mode("append").saveAsTable("main.ielts_demo.feature_lifecycle_events")
print(f"Feature Engineering table verified table={feature_table} primary_keys={verified_keys}")
