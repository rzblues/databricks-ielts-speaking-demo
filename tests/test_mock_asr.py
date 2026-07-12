from pathlib import Path

from ielts_scorer.asr import MockASRClient
from ielts_scorer.asr import asr_client_from_env
from ielts_scorer.audio_io import first_attempt


def test_mock_asr_returns_schema_segments():
    attempt = first_attempt(Path("sample_data"))
    segments = MockASRClient().transcribe(attempt)

    assert segments
    assert all(segment.attempt_id == attempt.attempt_id for segment in segments)


def test_asr_provider_selection_forbids_mock_when_real_required(monkeypatch):
    monkeypatch.setenv("REAL_AUDIO_REQUIRED", "true")
    monkeypatch.setenv("MOCK_ASR", "false")
    monkeypatch.setenv("ASR_PROVIDER", "mock")

    import pytest

    with pytest.raises(ValueError, match="forbids mock ASR"):
        asr_client_from_env()


def test_asr_provider_selection_local_whisper(monkeypatch):
    monkeypatch.setenv("REAL_AUDIO_REQUIRED", "true")
    monkeypatch.setenv("MOCK_ASR", "false")
    monkeypatch.setenv("ASR_PROVIDER", "local_whisper")

    assert asr_client_from_env().__class__.__name__ == "LocalWhisperASRClient"
