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
- Browser screenshot verification was unavailable in this run; App status and startup logs were verified through Databricks APIs.
- Automatic candidate-data retention/deletion is not configured; README documents explicit Volume and Delta deletion responsibilities.

## Pending Loop

No remaining M0-M6 task is pending.
