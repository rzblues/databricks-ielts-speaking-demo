import wave

import pytest

from ielts_scorer.audio_ingest import guard_real_audio_required


def make_wav(path):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x00" * 160)
    return path


def test_real_audio_required_forbids_mock_asr(tmp_path):
    audio = make_wav(tmp_path / "sample.wav")

    with pytest.raises(ValueError, match="forbids ASR_PROVIDER=mock"):
        guard_real_audio_required(audio, real_audio_required=True, asr_provider="mock")


def test_real_audio_required_fails_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        guard_real_audio_required(tmp_path / "missing.wav", real_audio_required=True, asr_provider="local_whisper")
