import wave

import pytest

from scripts import run_real_audio_demo


def make_wav(path):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x00" * 16000)
    return path


def test_run_real_audio_demo_rejects_mock_asr(monkeypatch, tmp_path):
    audio = make_wav(tmp_path / "sample.wav")
    monkeypatch.setenv("MOCK_ASR", "true")
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_real_audio_demo.py",
            "--audio-path",
            str(audio),
            "--attempt-id",
            "a",
            "--candidate-id",
            "c",
            "--question-id",
            "q",
            "--question-text",
            "Describe something.",
        ],
    )

    with pytest.raises(SystemExit, match="requires MOCK_ASR=false"):
        run_real_audio_demo.main()
