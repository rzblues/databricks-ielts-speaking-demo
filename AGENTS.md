# AGENTS.md

## Mission

Build a runnable Databricks demo for IELTS Speaking audio scoring.

The demo accepts or references a candidate speaking audio file, produces a transcript, extracts explainable speech and language features, estimates IELTS-style speaking bands, writes results to Delta tables, and displays the final report in a Streamlit or Databricks App.

## Product Positioning

This is an assessment assistant demo, not an official IELTS examiner.

Use the wording:
- "estimated IELTS-style band score"
- "demo assessment"
- "pronunciation / intelligibility estimate"

Do not use the wording:
- "official IELTS score"
- "certified examiner score"
- "guaranteed IELTS band"
- "phoneme-level pronunciation diagnosis" unless such model is actually implemented and validated.

## IELTS Scoring Dimensions

Use four dimensions:
1. Fluency and coherence
2. Lexical resource
3. Grammatical range and accuracy
4. Pronunciation / intelligibility estimate

The overall speaking estimate is the average of the four dimension bands, rounded to the nearest 0.5.

## Privacy And Data Handling

Candidate audio is user-generated personal data.

Rules:
- Do not commit real candidate audio.
- Do not log full audio bytes.
- Do not print secrets, tokens, or signed URLs.
- Use synthetic or mock audio in sample_data.
- Store audio paths and metadata, not audio payloads, in Delta tables.
- Make retention and deletion behavior explicit in README.
- Keep all outputs keyed by attempt_id.

## Engineering Constraints

Target Python 3.11 or newer. Local verification may use a newer compatible interpreter.

Keep core logic in:
src/ielts_scorer/

Keep notebooks thin. Notebooks should call package functions.

Required package modules:
- config.py
- schemas.py
- audio_io.py
- asr.py
- features.py
- rubric.py
- llm_client.py
- scoring.py
- delta_io.py
- report.py

Required app files:
- app/app.py
- app/app.yaml
- app/requirements.txt

Required notebooks:
- notebooks/00_setup.sql
- notebooks/01_ingest_audio.py
- notebooks/02_transcribe.py
- notebooks/03_extract_features.py
- notebooks/04_score_with_llm.py
- notebooks/05_review_results.py

Required docs:
- README.md
- docs/demo_script.md
- docs/loop_state.md
- docs/databricks_capability_probe.md
- docs/architecture.md

## Fallback Modes

The project must support these modes:

- MOCK_ASR=true
  Use sample_data/mock_transcripts.json instead of real ASR.

- MOCK_LLM=true
  Use deterministic local scoring output instead of Model Serving or external LLM.

- LOCAL_DEMO=true
  Run without Databricks by using local JSON or SQLite-like files.

- DATABRICKS_DEMO=true
  Use Databricks tables and, when available, Databricks app resources.

## Databricks Rules

Do not assume the workspace has full enterprise capabilities.

First probe:
- Current user
- Available catalogs and schemas
- Permission to create schema
- Permission to create tables
- Permission to create volume
- SQL warehouse availability
- Apps availability
- Model Serving availability
- Jobs availability
- Bundle availability

Prefer this namespace if available:
main.ielts_demo

If unavailable, detect and document the fallback namespace.

## Tables

Create or support these Delta tables:

attempts:
- attempt_id STRING
- candidate_id STRING
- question_id STRING
- question_text STRING
- audio_path STRING
- audio_format STRING
- duration_sec DOUBLE
- source STRING
- created_at TIMESTAMP

asr_segments:
- attempt_id STRING
- segment_id INT
- start_sec DOUBLE
- end_sec DOUBLE
- text STRING
- avg_logprob DOUBLE
- no_speech_prob DOUBLE
- created_at TIMESTAMP

speech_features:
- attempt_id STRING
- duration_sec DOUBLE
- speaking_sec DOUBLE
- silence_ratio DOUBLE
- words_count INT
- words_per_min DOUBLE
- pause_count INT
- long_pause_count INT
- avg_pause_sec DOUBLE
- filler_count INT
- filler_ratio DOUBLE
- repetition_count INT
- lexical_diversity DOUBLE
- avg_sentence_len DOUBLE
- complex_sentence_proxy DOUBLE
- asr_confidence_proxy DOUBLE
- created_at TIMESTAMP

scoring_results:
- attempt_id STRING
- overall_band DOUBLE
- fc_band DOUBLE
- lr_band DOUBLE
- gra_band DOUBLE
- p_band DOUBLE
- confidence DOUBLE
- json_report STRING
- model_endpoint STRING
- rubric_version STRING
- created_at TIMESTAMP

## Testing Rules

Tests must pass locally without Databricks.

Required tests:
- test_band_rounding.py
- test_features.py
- test_schema_validation.py
- test_mock_scoring.py
- test_report_rendering.py

Run:
python -m pytest -q

If tests fail, fix before adding new features.

## Definition Of Done

The task is done only when:

1. Local mock demo runs end-to-end.
2. Tests pass.
3. Databricks setup notebook or SQL creates required tables.
4. At least one sample attempt flows through:
   attempts -> asr_segments -> speech_features -> scoring_results.
5. Streamlit app displays:
   - overall score
   - four dimension scores
   - transcript
   - extracted features
   - evidence
   - feedback
   - caveat that this is an estimated demo score
6. README explains setup, fallback modes, Databricks deployment, and demo script.
7. docs/loop_state.md contains final status and known limitations.

## Real-Audio Golden Path Rules

The previous mock vertical slice is useful but not sufficient for the customer demo.

The customer demo golden path must use:
- real audio bytes
- a real audio file path
- non-mock ASR
- Delta records linked by attempt_id
- visible provider provenance in the App

Mock ASR and mock scoring are allowed only as fallback or local development mode.

When `REAL_AUDIO_REQUIRED=true`:
- Missing audio file must fail.
- Empty ASR transcript must fail.
- ASR provider `mock` must fail.
- Nonexistent sample audio path must fail.
- The pipeline must not silently use `sample_data/mock_transcripts.json`.

When `MOCK_ASR=true`:
- The UI and report must visibly say `Mock ASR`.
- The result must not be presented as real-audio ASR output.

When `MOCK_LLM=true`:
- The UI and report must visibly say `Rule-based mock scoring`.
- The result must not be presented as model-scored output.

Every report must include:
- audio_source
- asr_provider
- asr_is_mock
- scoring_provider
- scoring_is_mock
- pipeline_mode
