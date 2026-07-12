import wave

import pytest

from ielts_scorer.audio_preprocess import inspect_wav, preprocess_for_asr


def make_wav(path, sample_rate=8000, channels=1):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * sample_rate)
    return path


def test_inspect_wav_metadata(tmp_path):
    audio = make_wav(tmp_path / "sample.wav", sample_rate=16000)

    metadata = inspect_wav(audio)

    assert metadata.duration_sec == 1.0
    assert metadata.sample_rate_hz == 16000
    assert metadata.channels == 1


def test_preprocess_wav_outputs_mono_16k(tmp_path):
    audio = make_wav(tmp_path / "sample.wav", sample_rate=8000)

    processed = preprocess_for_asr(audio, tmp_path / "processed")

    metadata = inspect_wav(processed)
    assert metadata.sample_rate_hz == 16000
    assert metadata.channels == 1


def test_preprocess_missing_file_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        preprocess_for_asr(tmp_path / "missing.wav", tmp_path / "processed")
