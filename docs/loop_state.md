# Loop State

## Current Classification

`FULL_DATABRICKS_DEMO`

The customer path is Databricks-first. Local JSON and mock providers remain test/fallback modes only.

## 2026-07-10 Repair Loop M0-M6

| Milestone | Status | Evidence |
|---|---|---|
| M0 - regression baseline | completed | 13 expected failures reproduced; final `45 passed` |
| M1 - contracts and provenance | completed | Overall/dimension invariants, provider consistency, strict model payload validation, SQL polling |
| M2 - Databricks App | completed | Strict no-sample fallback, safe upload paths, cached Whisper client, per-run updates, deployment `01f17c129f14158d9ff1d9745e7e5e13` |
| M3 - real model path | completed | Job run `77694632817502`: real Volume audio, `local_whisper`, `databricks-gpt-oss-20b`, all tasks SUCCESS |
| M4 - Feature Engineering and quality | completed | `speech_feature_table_pk(attempt_id)`, 8 latest checks PASS, Lakehouse monitor ACTIVE |
| M5 - MLflow and SQL AI | completed | MLflow run `4800f2caffa342cf8b3e1d6e1f6f6e25` FINISHED; SQL AI positive/fluent |
| M6 - deployment acceptance | completed | App RUNNING/ACTIVE, Job deployed with failure email, endpoint READY, Delta attempt chain verified |

## Golden Attempt Evidence

- Attempt: `attempt_real_final`
- Audio: `/Volumes/main/ielts_demo/ielts_audio/attempt_real_final.wav`, 17.91 seconds
- Whisper weights: `/Volumes/main/ielts_demo/ielts_audio/models/tiny.en.pt`
- ASR: 5 segments, provider `local_whisper`, `asr_is_mock=false`
- Features: 58 words, 194.305 words/min, lexical diversity 0.7931
- Score: overall 5.5; FC 5.5, LR 5.5, GRA 5.5, P 6.0
- Scoring: `databricks_model_serving:databricks-gpt-oss-20b`, `scoring_is_mock=false`
- Processing run: `run_68f42d602ff944448f1af2521e062fdf`, status `COMPLETED`
- Quality: latest 8 checks PASS, 0 FAIL
- Feature Engineering: primary key constraint `speech_feature_table_pk(attempt_id)`

## Deployment Evidence

```text
python -m pytest -q
45 passed

databricks bundle validate
Validation OK!

databricks bundle run ielts_speaking_demo_pipeline
run_id=77694632817502
result=SUCCESS

databricks apps get ielts-speaking-demo
app_status=RUNNING
compute_status=ACTIVE
deployment=01f17c129f14158d9ff1d9745e7e5e13

databricks serving-endpoints get databricks-gpt-oss-20b
ready=READY

databricks quality-monitors get main.ielts_demo.speech_features
status=MONITOR_STATUS_ACTIVE
```

## Known Limitations

- `databricks-gpt-oss-20b` is a generic foundation model prompted with the demo rubric, not a validated IELTS examiner model.
- Pronunciation remains an ASR/timing-based intelligibility estimate, not phoneme-level diagnosis.
- This workspace supports Serverless Jobs only and limits active Serverless runs to one; the verified Whisper task took about 295 seconds.
- Local browser screenshot verification passed; automated access to the deployed App still requires an interactive Databricks sign-in.
- Automatic candidate-data retention/deletion is not configured; README documents explicit Volume and Delta deletion responsibilities.

## 2026-07-14 App Upload Repair

- Reproduced: App code attempted a local filesystem write under `/Volumes`, which failed with `Permission denied`.
- Fixed: uploaded bytes now use the Databricks Files API; Whisper receives a temporary local audio copy and a cached local copy of the Volume-hosted model.
- UI: upload instructions use explicit dark text, stale reruns no longer dim the page, and report loading plus Whisper processing show staged status and progress.
- Verification: `54 passed`; browser screenshot and console check passed; Files API upload/download probe passed and was deleted afterward.
- Deployment: `01f17f8cb25618e28cb872dce3e03fce`, status `SUCCEEDED`; App `RUNNING`; compute `ACTIVE`.
- Privacy cleanup: removed stale `sample_data/audio/real_demo.wav` from the Workspace deployment source; only the synthetic sample remains.

## 2026-07-14 Non-WAV ASR And UI Repair

- Reproduced from Delta: `attempt_real_app_001` failed because the App image had no system `ffprobe` for the uploaded non-WAV file.
- Fixed: `imageio-ffmpeg` supplies a bundled executable; preprocessing converts MP3/M4A/FLAC directly to mono 16 kHz WAV without a separate `ffprobe` dependency and exposes ffmpeg to Whisper through PATH.
- Workflow: selecting a file creates a new editable attempt ID; the separate Register action was removed, and `Run speaking assessment` now performs registration plus ASR as one transaction from the user's perspective.
- UI: uploaded-file, status, alert, caption, and dropzone text use explicit readable colors; the only white text found by computed-style inspection is the primary-button label on its red background.
- Verification: `56 passed`; bundled-ffmpeg probe passed with an empty system PATH; real M4A-to-WAV conversion passed; browser upload confirmed the generated attempt ID and single enabled action.
- Deployment: `01f17f8ebb0f1d349bfd66ea373d9a9b`, status `SUCCEEDED`; App `RUNNING`; compute `ACTIVE`; build log confirms `imageio-ffmpeg-0.6.0` installed.

## Pending Loop

No remaining M0-M6 task is pending.
