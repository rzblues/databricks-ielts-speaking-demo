# Databricks Capability Probe

## Probe Timestamp

2026-07-10 Asia/Singapore

## Local Environment

- Python command `python`: unavailable on shell PATH.
- System `python3`: Python 3.9.6.
- Verification Python: Python 3.12.13 from the Codex bundled runtime.
- OS: macOS-26.5.1-arm64-arm-64bit.
- Package manager: pip 26.0.1 with the bundled Python runtime.
- Databricks CLI available: yes, Databricks CLI v1.2.1.
- Databricks SDK available in App requirements: yes.
- Databricks Bundles command available: yes, `databricks bundle --help` succeeded.

## Auth

- Auth available: yes after user reauthenticated.
- Current user: available through `databricks current-user me`.
- Workspace URL detected: not printed by probe to avoid leaking configuration.
- Auth method: DEFAULT profile.

## Unity Catalog

- SHOW CATALOGS works: yes.
- Preferred catalog exists: yes, `main`.
- Can create schema: yes, `main.ielts_demo`.
- Can create tables: yes, `attempts`, `asr_segments`, `speech_features`, `scoring_results`.
- Can create volume: yes, `main.ielts_demo.ielts_audio`.
- Selected namespace: `main.ielts_demo`.

## Compute

- SQL warehouse available: yes, `Serverless Starter Warehouse` exists and was stopped during probe.
- Job compute available: yes, Serverless Jobs only.
- Classic job clusters: unavailable; the workspace rejects them with `Only serverless compute is supported in the workspace`.
- Deployed Job: `ielts-speaking-demo-pipeline`, job id `799248163445242`.

## Apps

- Databricks Apps available: yes.
- Can deploy app: yes, `ielts-speaking-demo` deployed successfully.
- App URL: `https://ielts-speaking-demo-7474646798897087.aws.databricksapps.com`.

## Model Serving / Foundation Model

- Serving endpoints list works: yes.
- Existing endpoint selected by this demo: `databricks-gpt-oss-20b`.
- Foundation Model API available: yes, verified through Model Serving chat invocation.
- External model endpoint available: not probed.
- Scoring fallback: deterministic mock scorer remains available and visibly labeled.

## Final Environment Classification

FULL_DATABRICKS_DEMO

## Manual Steps Needed From User

- Open the Databricks App URL in an authenticated browser session.
- For production scoring, replace the generic foundation-model prompt with a validated IELTS-specific model/calibration workflow while keeping the same table schema.
