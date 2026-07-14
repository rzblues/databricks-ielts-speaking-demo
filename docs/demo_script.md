# Demo Script

## Opening

This demo shows how Databricks can govern the evidence chain for an IELTS Speaking style assessment. The user starts with a speaking audio attempt. The system stores metadata, produces transcript segments, extracts measurable features, estimates four IELTS-style dimensions, and displays an explainable report.

## What The Customer Sees

1. A candidate attempt identified by `attempt_id`.
2. Transcript segments with timestamps.
3. Speech and language features such as words per minute, pauses, filler ratio, lexical diversity, sentence length, and ASR confidence proxy.
4. Four estimated IELTS-style scores:
   - Fluency and coherence
   - Lexical resource
   - Grammatical range and accuracy
   - Pronunciation / intelligibility estimate
5. Evidence and feedback for each score.
6. A clear caveat that the output is a demo estimate.
7. Databricks ML Platform provenance: Model Serving provider, SQL AI transcript label, and quality-check summary.

## What Databricks Stores

The intended Delta tables are:

- `main.ielts_demo.attempts`
- `main.ielts_demo.asr_segments`
- `main.ielts_demo.speech_features`
- `main.ielts_demo.scoring_results`
- `main.ielts_demo.speech_feature_table`
- `main.ielts_demo.feature_lifecycle_events`
- `main.ielts_demo.quality_check_results`
- `main.ielts_demo.ai_function_insights`

The local fallback writes the same logical records to `outputs/local_tables/*.jsonl`.

## Why The Scores Were Given

The fallback mock scorer is deterministic:

- Fluency uses speech rate, silence ratio, fillers, long pauses, and repetition.
- Lexical resource uses word count, lexical diversity, and filler ratio.
- Grammar uses average sentence length and a complex-sentence proxy.
- Pronunciation uses an ASR confidence proxy and timing-based intelligibility signals.

The enhanced Databricks path can call a live Model Serving endpoint, record `scoring_is_mock=false`, then log band and feature metrics to MLflow. SQL AI functions add a lightweight sentiment and delivery label to help explain how Databricks-native AI can enrich the transcript workflow.

## Production Path

To make this production-grade:

- Validate and calibrate the included Whisper ASR path against representative speaking audio.
- Replace demo Model Serving prompts with a validated rubric-aligned model.
- Add human review and calibration data.
- Add retention/deletion policies for candidate audio.
- Deploy with Databricks Apps, Jobs, Unity Catalog permissions, Lakehouse Monitoring, MLflow model registry, and audit logging.

## Real-Audio Upgrade

The App includes a one-step real-audio panel. Selecting a file generates a new editable attempt ID. `Run speaking assessment` stores the audio under the `main.ielts_demo.ielts_audio` Volume, records the attempt and processing run, runs Whisper on App compute, and labels its rule-based score as mock; the Serverless Job path runs the full chain through live Model Serving.
