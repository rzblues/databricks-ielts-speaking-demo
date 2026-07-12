-- Databricks notebook source
-- Databricks setup SQL for IELTS Speaking demo.
-- Preferred namespace: main.ielts_demo.
-- If this fails in Free Edition, create a schema where you have permission and update notebook variables.

USE CATALOG main;
CREATE SCHEMA IF NOT EXISTS ielts_demo;
USE SCHEMA ielts_demo;

CREATE TABLE IF NOT EXISTS attempts (
  attempt_id STRING,
  candidate_id STRING,
  question_id STRING,
  question_text STRING,
  audio_path STRING,
  audio_format STRING,
  duration_sec DOUBLE,
  source STRING,
  created_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS asr_segments (
  attempt_id STRING,
  segment_id INT,
  start_sec DOUBLE,
  end_sec DOUBLE,
  text STRING,
  avg_logprob DOUBLE,
  no_speech_prob DOUBLE,
  created_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS speech_features (
  attempt_id STRING,
  duration_sec DOUBLE,
  speaking_sec DOUBLE,
  silence_ratio DOUBLE,
  words_count INT,
  words_per_min DOUBLE,
  pause_count INT,
  long_pause_count INT,
  avg_pause_sec DOUBLE,
  filler_count INT,
  filler_ratio DOUBLE,
  repetition_count INT,
  lexical_diversity DOUBLE,
  avg_sentence_len DOUBLE,
  complex_sentence_proxy DOUBLE,
  asr_confidence_proxy DOUBLE,
  created_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS scoring_results (
  attempt_id STRING,
  overall_band DOUBLE,
  fc_band DOUBLE,
  lr_band DOUBLE,
  gra_band DOUBLE,
  p_band DOUBLE,
  confidence DOUBLE,
  json_report STRING,
  model_endpoint STRING,
  rubric_version STRING,
  audio_source STRING,
  asr_provider STRING,
  asr_is_mock BOOLEAN,
  scoring_provider STRING,
  scoring_is_mock BOOLEAN,
  pipeline_mode STRING,
  created_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS processing_runs (
  run_id STRING,
  attempt_id STRING,
  pipeline_mode STRING,
  audio_path STRING,
  audio_exists BOOLEAN,
  audio_sha256 STRING,
  audio_size_bytes BIGINT,
  asr_provider STRING,
  asr_is_mock BOOLEAN,
  scoring_provider STRING,
  scoring_is_mock BOOLEAN,
  processing_status STRING,
  error_message STRING,
  created_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS feature_lifecycle_events (
  event_time TIMESTAMP,
  feature_table STRING,
  attempt_id STRING,
  feature_version STRING,
  source_table STRING,
  sdk_available BOOLEAN,
  quality_status STRING,
  notes STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS quality_check_results (
  check_time TIMESTAMP,
  check_name STRING,
  status STRING,
  failing_rows BIGINT,
  expectation_sql STRING,
  notes STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS ai_function_insights (
  created_at TIMESTAMP,
  attempt_id STRING,
  sentiment STRING,
  delivery_label STRING,
  transcript_preview STRING,
  provider STRING,
  is_mock BOOLEAN,
  notes STRING
) USING DELTA;
