# Known Limitations

- The fallback scorer is deterministic and heuristic; it remains visibly labeled as mock.
- Pronunciation is an intelligibility estimate based on ASR confidence and timing, not phoneme-level pronunciation analysis.
- Mock transcript data is synthetic and does not include real audio bytes.
- Databricks Model Serving is wired and verified with `databricks-gpt-oss-20b`, but this is still a generic foundation model prompt rather than a validated IELTS examiner model.
- The Databricks App is deployed and running, but browser-level rendering was not screenshot-verified in this run.
- Whisper ASR uses the `tiny.en` weights stored in a Unity Catalog Volume for demo stability. The verified Serverless task took about 295 seconds for 17.91 seconds of audio.
- The workspace permits Serverless Jobs only and currently enforces one active Serverless run at a time.
- Candidate-data retention/deletion is documented but not automatically scheduled.
