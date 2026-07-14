import wave
from types import SimpleNamespace

import pytest

from ielts_scorer import audio_preprocess
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


def test_preprocess_non_wav_uses_bundled_ffmpeg_without_ffprobe(tmp_path, monkeypatch):
    audio = tmp_path / "answer.m4a"
    audio.write_bytes(b"synthetic-m4a-placeholder")
    commands = []

    def fake_run(command, **_kwargs):
        commands.append(command)
        make_wav(tmp_path / "processed" / "answer.mono16k.wav", sample_rate=16000)
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(audio_preprocess, "ensure_ffmpeg_on_path", lambda: "/bundled/ffmpeg")
    monkeypatch.setattr(audio_preprocess.subprocess, "run", fake_run)
    monkeypatch.setattr(audio_preprocess.shutil, "which", lambda name: None if name == "ffprobe" else None)

    processed = preprocess_for_asr(audio, tmp_path / "processed")

    assert processed.name == "answer.mono16k.wav"
    assert commands[0][0] == "/bundled/ffmpeg"
    assert inspect_wav(processed).sample_rate_hz == 16000
