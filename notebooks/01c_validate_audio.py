# Databricks notebook source

"""Validate audio metadata before ASR.

This notebook is a thin wrapper placeholder for R7. In Databricks, use widgets to
provide a Volume path and then call package preprocessing functions on cluster
local paths when available.
"""

dbutils.widgets.text("audio_path", "")
dbutils.widgets.text("attempt_id", "attempt_real_001")

audio_path = dbutils.widgets.get("audio_path")
attempt_id = dbutils.widgets.get("attempt_id")
print({"attempt_id": attempt_id, "audio_path": audio_path, "next": "run real ASR with ASR_PROVIDER=local_whisper"})
