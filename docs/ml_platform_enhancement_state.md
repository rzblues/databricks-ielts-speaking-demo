# ML Platform Enhancement State

Date: 2026-07-10

## Target Namespace

- Catalog/schema: `main.ielts_demo`
- SQL warehouse: `77cea25dcd8171c6`
- Databricks App: `ielts-speaking-demo`

## Added Platform Assets

| Area | Asset | Purpose |
|---|---|---|
| MLflow | `notebooks/06_log_mlflow_baseline.py` | Logs band/feature metrics for the job `attempt_id`; the run context closes with a terminal status. |
| Model Serving | `scripts/score_with_model_serving.py` | Calls a Databricks Model Serving chat endpoint and writes a model-scored `scoring_results` row. |
| Feature Engineering | `main.ielts_demo.speech_feature_table` | Registered and merged by `FeatureEngineeringClient`, keyed by `attempt_id`. |
| Feature lifecycle | `main.ielts_demo.feature_lifecycle_events` | Audit trail for feature publish events and SDK availability. |
| Monitoring | `main.ielts_demo.quality_check_results` | Stores SQL expectation results for tables and provenance. |
| Monitoring | Databricks quality monitor attempt | `scripts/run_quality_checks.py` attempts to create a monitor on `speech_features`. |
| SQL AI | `main.ielts_demo.ai_function_insights` | Stores `ai_analyze_sentiment` and `ai_classify` transcript insights. |
| Jobs | `resources/jobs.yml` | Serverless end-to-end task graph with one shared `attempt_id` and `on_failure` email notifications. |
| App | `app/app.py` | Adds a Databricks ML Platform panel for Model Serving, SQL AI, and quality checks. |

## Commands

Primary execution path for `attempt_real_final`:

```bash
databricks bundle deploy
databricks bundle run ielts_speaking_demo_pipeline
python3 -m pytest -q
databricks bundle validate
databricks sync . /Workspace/Users/<workspace-user>/ielts-speaking-demo-app-src --full ...
databricks apps deploy ielts-speaking-demo --source-code-path /Workspace/Users/<workspace-user>/ielts-speaking-demo-app-src
databricks apps get ielts-speaking-demo -o json
```

## Execution Evidence

- MLflow experiment: `/Users/<workspace-user>/ielts-speaking-demo/ml-platform-enhancement`
- MLflow experiment id: `1476205543154015`
- Latest MLflow run id: `4800f2caffa342cf8b3e1d6e1f6f6e25`, status `FINISHED`
- Model Serving endpoint: `databricks-gpt-oss-20b`
- Latest real-audio model-scored attempt: `attempt_real_final`
- Latest overall band: `5.5`
- Latest scoring provider: `databricks_model_serving:databricks-gpt-oss-20b`
- Latest scoring mock flag: `false`
- Feature table: `main.ielts_demo.speech_feature_table`, 1 row / 1 distinct attempt, primary key `speech_feature_table_pk(attempt_id)`
- SQL quality checks: latest 8 PASS, 0 FAIL
- Lakehouse monitor: created for `main.ielts_demo.speech_features`
- SQL AI latest result: sentiment `positive`, delivery label `fluent`
- Tests: 45 passed
- Bundle validation: OK
- App deployment: `01f17c129f14158d9ff1d9745e7e5e13`, state `SUCCEEDED`
- App source path: `/Workspace/Users/<workspace-user>/ielts-speaking-demo-app-src`
- Job: `ielts-speaking-demo-pipeline` (`799248163445242`), Serverless-only compute
- Job run: `77694632817502`, result `SUCCESS`

## Expected Demo Story

1. A real audio attempt is registered and transcribed into Delta.
2. Engineered features are published to `speech_feature_table`.
3. Databricks Model Serving produces an estimated IELTS-style score.
4. SQL AI functions add sentiment and delivery labels for quick explainability.
5. Quality checks and monitor setup show governance readiness.
6. MLflow stores the scoring/feature metrics for experiment tracking.
