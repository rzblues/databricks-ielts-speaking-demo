# REAL_AUDIO_ASR_LOOP.md

## Loop Name

Real Audio / Real ASR Upgrade Loop

## Why This Loop Exists

The current Databricks IELTS demo proves the Lakehouse data flow and App UI, but it does not yet prove real user audio processing.

Current limitations:
- No real audio bytes exist in the repository or Databricks Volume.
- `sample_data/audio/sample_candidate_response.wav` is referenced but missing.
- ASR defaults to `MockASRClient`.
- Scoring defaults to deterministic mock scoring.
- The App must make provider provenance visible so mock and real outputs cannot be confused.

This loop upgrades the demo from a Databricks-first skeleton to a real-audio-first MVP.

## North Star

A customer can upload or register an actual speaking audio file and see:

real audio file -> Databricks Volume path -> real ASR transcript with timestamps -> extracted speech/language features -> IELTS-style scoring report -> Delta tables -> Streamlit / Databricks App display.

## Non-Goals

- Do not build a production pronunciation model.
- Do not train a custom ASR model.
- Do not fine-tune an IELTS scoring LLM.
- Do not remove mock fallback.
- Do not claim official IELTS scoring.

## Hard Rule

Mock mode is allowed as fallback, but the golden path must use real audio and real ASR.

A completed real-audio demo must prove:
- A real audio file exists.
- Audio bytes are stored or accessible.
- The attempt row points to a real audio path.
- ASR provider is not `mock`.
- ASR output was generated from the real audio file.
- The transcript and score are linked by the same `attempt_id`.

## New Environment Flags

```bash
DEMO_MODE=real_audio
REAL_AUDIO_REQUIRED=true
MOCK_ASR=false
MOCK_LLM=true
ASR_PROVIDER=local_whisper
LLM_PROVIDER=mock
```

Optional future flags:

```bash
ASR_PROVIDER=databricks_multimodal
LLM_PROVIDER=databricks_foundation
```

## Required Metadata Additions

Use companion table `main.ielts_demo.processing_runs`:

- run_id STRING
- attempt_id STRING
- pipeline_mode STRING
- audio_path STRING
- audio_exists BOOLEAN
- audio_sha256 STRING
- audio_size_bytes BIGINT
- asr_provider STRING
- asr_is_mock BOOLEAN
- scoring_provider STRING
- scoring_is_mock BOOLEAN
- processing_status STRING
- error_message STRING
- created_at TIMESTAMP

## Loop R0: Audit Current State

Goal:
Confirm the current project state without changing product behavior.

Build:
- Add `scripts/audit_demo_state.py`.
- Check local sample audio existence, Databricks Volume availability, mock/real provider state, and whether the App exposes provider information.
- Write `docs/real_audio_upgrade_state.md`.

Exit criteria:
- `docs/real_audio_upgrade_state.md` exists.
- It clearly states what is real and what is mock.
- No feature work begins until this audit is written.

## Loop R1: Real Audio Ingestion Contract

Goal:
Make real audio a first-class input.

Build:
- Add `src/ielts_scorer/audio_ingest.py`.
- Add `src/ielts_scorer/provider_provenance.py`.
- Add `scripts/register_real_audio_attempt.py`.
- Add `notebooks/01b_register_real_audio.py`.
- Add `processing_runs` metadata support.

Required script:

```bash
python scripts/register_real_audio_attempt.py \
  --audio-path /path/to/local.wav \
  --candidate-id demo_candidate_real_001 \
  --question-id part2_problem \
  --question-text "Describe a time you solved a difficult problem." \
  --attempt-id attempt_real_001
```

Behavior:
- Validate that the local audio file exists.
- Validate extension: `.wav`, `.mp3`, `.m4a`, or `.flac`.
- For the first stable version, require `.wav` for real ASR if conversion is unavailable.
- Compute `audio_sha256`.
- Compute file size.
- Copy/upload to Databricks Volume when Databricks is available.
- If Databricks upload is unavailable, keep local path and mark fallback.
- Insert or upsert the attempt metadata.
- Insert a `processing_runs` record.

Exit criteria:
- One real audio attempt can be registered.
- Attempt metadata points to an existing audio path.
- Missing audio path causes a hard failure in `REAL_AUDIO_REQUIRED=true`.

## Loop R2: Audio Validation And Preprocessing

Implement audio metadata extraction and optional WAV normalization. Do not overwrite user audio.

## Loop R3: Real ASR Client

Implement `LocalWhisperASRClient` provider selection. Do not silently fallback to mock when `REAL_AUDIO_REQUIRED=true`.

## Loop R4: Real Audio Vertical Slice

Run `real audio -> register -> validate -> real ASR -> features -> scoring -> Delta -> report`.

## Loop R5: Provider Provenance In Delta And App

Display visible `REAL AUDIO`, `REAL ASR`, `MOCK SCORING`, and `DEMO ESTIMATE` badges.

## Loop R6: Optional Real LLM Scoring

Add real LLM provider selection only after real audio and real ASR work.

## Loop R7: Databricks Notebook Path

Make the real-audio path runnable notebook-by-notebook in Databricks.

## Loop R8: App Upload Or Register Path

Let the App either upload to Volume or register an existing Volume path.

## Loop R9: Real-Audio Demo Hardening

Update docs and customer narrative.

## Loop R10: Final Real-Audio Verification

Prove one complete real-audio attempt with non-mock ASR and provider badges.
