# Databricks ML Platform Enhancement Loop

This loop upgrades the IELTS Speaking demo from a mock-first Databricks app into a Databricks ML Platform demo with traceable platform assets.

## Success Criteria

- M0 records current Databricks capabilities with concrete evidence.
- M1 logs the latest scoring output to Databricks MLflow tracking.
- M2 scores at least one attempt through a Databricks Model Serving endpoint and writes `scoring_is_mock=false`.
- M3 publishes `speech_features` into a managed feature lifecycle table.
- M4 writes SQL quality expectations and attempts Lakehouse/Data Quality Monitor setup.
- M5 writes SQL AI function insights using `ai_analyze_sentiment` and `ai_classify`.
- M6 updates App/docs/job wiring and verifies tests plus bundle validation.

## Loop Order

| Milestone | Status | Command / Evidence |
|---|---|---|
| M0 Capability probe | completed | `databricks serving-endpoints list -o json`; `databricks experiments search-experiments -o json`; `databricks quality-monitors --help`; SQL AI probe |
| M1 MLflow tracking | completed | `ATTEMPT_ID=attempt_real_final ... scripts/log_mlflow_baseline.py`; experiment `1476205543154015`; run `2e8f82880d244853aba3017b52106899` |
| M2 Model Serving scoring | completed | `DATABRICKS_MODEL_ENDPOINT=databricks-gpt-oss-20b ... scripts/score_with_model_serving.py`; latest `attempt_real_final` overall `6.0`, `scoring_is_mock=false` |
| M3 Feature lifecycle | completed | `scripts/publish_feature_table.py`; `main.ielts_demo.speech_feature_table` has 2 rows / 2 attempts |
| M4 Monitoring and alerts | completed | `scripts/run_quality_checks.py`; 6 SQL checks PASS; Lakehouse monitor created for `main.ielts_demo.speech_features`; bundle job has `on_failure` notification |
| M5 SQL AI functions | completed | `ATTEMPT_ID=attempt_real_final ... scripts/run_sql_ai_insights.py`; sentiment `positive`, delivery label `fluent` |
| M6 Final verification | completed | `python3 -m pytest -q` -> 33 passed; `databricks bundle validate` -> OK; App deployment `01f179e7804f1c6ab53b30bde17e9d5c` SUCCEEDED/RUNNING |

## M0 Capability Facts

- Model Serving is available. Workspace endpoints include `databricks-gpt-oss-20b`, `databricks-gpt-oss-120b`, `databricks-claude-sonnet-5`, and embedding endpoints.
- MLflow tracking APIs are available through the Databricks `experiments` CLI group.
- SQL AI functions are available on warehouse `77cea25dcd8171c6`; `ai_analyze_sentiment('I enjoyed the lesson')` returned `positive`, and `ai_classify(...)` returned a label.
- Lakehouse Monitoring CLI is available as `databricks quality-monitors`, with a deprecation note pointing to the Data Quality Monitors API.
- The local Python environment does not currently have `mlflow`, `databricks-sdk`, `databricks.feature_engineering`, or `sklearn`; platform scripts must not make local tests depend on these packages.

## Guardrails

- The App must continue to show that this is an estimated IELTS-style demo assessment.
- Mock ASR or mock scoring must remain visible in provider provenance.
- Real Model Serving scoring must be written with `scoring_is_mock=false`.
- Platform failures must be recorded as warnings or failures; they must not be silently converted to mock success.
