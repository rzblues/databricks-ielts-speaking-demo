# Architecture

## Flow

```text
audio attempt metadata
  -> ASRClient
  -> ASRSegment records
  -> extract_features
  -> SpeechFeatures record
  -> Databricks Model Serving scorer or mock scorer
  -> ScoringReport
  -> Delta tables, MLflow, feature lifecycle, SQL AI insights, or local JSONL fallback
  -> Streamlit / Databricks App report
```

## Evidence Chain

Every output is keyed by `attempt_id`:

- `attempts`: candidate, question, audio path, format, duration.
- `asr_segments`: transcript text with timestamps and ASR confidence proxies.
- `speech_features`: explainable numeric signals used by scoring.
- `scoring_results`: estimated IELTS-style scores and JSON report.
- `speech_feature_table`: Databricks Feature Engineering table keyed by `attempt_id`.
- `quality_check_results`: expectation outcomes for table and provenance health.
- `ai_function_insights`: Databricks SQL AI sentiment and delivery labels.

## Boundaries

- `asr.py`: mock ASR by default; optional local Whisper client.
- `features.py`: deterministic, explainable feature extraction.
- `llm_client.py`: mock scorer by default; optional Databricks Model Serving client.
- `model_serving.py`: Databricks Model Serving chat endpoint invocation and report validation.
- `delta_io.py`: Databricks table contract plus local JSONL fallback.
- `app/app.py`: Streamlit UI that imports without Streamlit for smoke tests.
- `audio_preprocess.py`: validates audio metadata and creates mono 16k WAV derived files.
- `run_real_audio_demo.py`: real-audio path with non-mock ASR and mock scoring.

## ML Platform Layer

- MLflow tracking records scoring metrics, feature metrics, provider tags, and attempt identifiers.
- The App and Serverless Job real-audio paths use a live Databricks-hosted Model Serving endpoint; rule-based scoring remains a local fallback only.
- `notebooks/07_publish_feature_table.py` registers and merges `speech_features` through `FeatureEngineeringClient`; the manual script is explicitly a Delta-only fallback.
- Monitoring runs SQL expectations and attempts a Lakehouse/Data Quality monitor on the source feature table.
- SQL AI functions enrich transcripts with native `ai_analyze_sentiment` and `ai_classify` outputs.

## Scoring Caveat

The demo estimates IELTS-style bands for customer demonstration. It does not claim official IELTS scoring, certified examiner scoring, or phoneme-level pronunciation diagnosis.
