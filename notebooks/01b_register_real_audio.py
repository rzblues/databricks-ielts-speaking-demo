# Databricks notebook source

"""Register a real audio attempt.

Widgets expected:
- audio_path
- attempt_id
- candidate_id
- question_id
- question_text
- asr_provider
"""

dbutils.widgets.text("audio_path", "")
dbutils.widgets.text("attempt_id", "attempt_real_001")
dbutils.widgets.text("candidate_id", "demo_candidate_real_001")
dbutils.widgets.text("question_id", "part2_problem")
dbutils.widgets.text("question_text", "Describe a time you solved a difficult problem.")
dbutils.widgets.text("asr_provider", "local_whisper")

print("Use scripts/register_real_audio_attempt.py for CLI registration, or port the same package calls here in R7.")
