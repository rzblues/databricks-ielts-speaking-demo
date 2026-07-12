# Real Audio Upgrade State

Audit timestamp: 2026-07-02T11:51:05

## R0 Audit Findings

- Sample attempt id: `attempt_sample_001`
- Sample audio path: `sample_data/audio/sample_candidate_response.wav`
- Sample audio exists locally: `False`
- Current sample transcript source: `sample_data/mock_transcripts.json`
- Current ASR golden path status: `mock`
- Current scoring status: `rule_based_mock`
- Databricks Volume `main.ielts_demo.ielts_audio` available: `True`
- App exposes provider badges: `True`

## Databricks Table Counts

- `attempts`: 3
- `asr_segments`: 10
- `speech_features`: 2
- `scoring_results`: 2
- `processing_runs`: 3

## R0 Conclusion

The existing Databricks demo is real for schema, Delta tables, Volume, and App deployment, but still mock for audio bytes, ASR transcript, and scoring.
R1 must make real audio registration a first-class path and must not treat the missing sample WAV as valid input.

## R1 Status

- Real audio registration script: `scripts/register_real_audio_attempt.py`
- Registered smoke attempt: `attempt_real_r1`
- Registered smoke attempt audio path: `/Volumes/main/ielts_demo/ielts_audio/attempt_real_r1.wav`
- Registered smoke processing status: `REGISTERED`
- Missing audio guardrail: verified hard failure with clear `ERROR: audio file does not exist` message.

## R2-R5 Status

- Audio preprocessing module: `src/ielts_scorer/audio_preprocess.py`
- Real ASR provider: `LocalWhisperASRClient` using `openai-whisper`
- Databricks compute path: App requirements include `openai-whisper`; deployment logs confirm `openai-whisper` and Torch installed on Databricks App compute.
- Notebook/job path: `notebooks/02_transcribe.py` installs `openai-whisper` on Databricks cluster compute; bundle validates.
- App upload/register button: implemented.
- App process button: implemented, runs Whisper on Databricks App compute.
- Verified real-ASR attempt: `attempt_real_final`
- Verified real-ASR attempt audio path: `/Volumes/main/ielts_demo/ielts_audio/attempt_real_final.wav`
- Verified ASR segments count: `5`
- Verified processing status: `COMPLETED`
- Verified provenance: `real_audio / local_whisper / asr_is_mock=false / rule_based_mock / scoring_is_mock=true`

## R8-R10 Status

- Databricks App URL: `https://ielts-speaking-demo-7474646798897087.aws.databricksapps.com`
- App deployment status: `SUCCEEDED`
- App runtime status: `RUNNING`
- Final tests: `32 passed`
- Bundle validation: `Validation OK`
