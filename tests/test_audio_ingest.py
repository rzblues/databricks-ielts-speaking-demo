import wave
from pathlib import Path

import pytest

from ielts_scorer.audio_ingest import validate_audio_file, volume_destination


def make_wav(path: Path) -> Path:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x00" * 160)
    return path


def test_validate_audio_file_hashes_nonempty_wav(tmp_path):
    audio = make_wav(tmp_path / "sample.wav")
    metadata = validate_audio_file(audio, require_wav_for_real_asr=True)

    assert metadata.audio_exists is True
    assert metadata.audio_format == "wav"
    assert len(metadata.audio_sha256) == 64
    assert metadata.audio_size_bytes > 0


def test_missing_audio_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        validate_audio_file(tmp_path / "missing.wav")


def test_unsupported_extension_fails(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("not audio", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported audio extension"):
        validate_audio_file(path)


def test_volume_destination_uses_attempt_id():
    assert volume_destination("attempt_real_001", Path("voice.wav")).endswith("/attempt_real_001.wav")


@pytest.mark.parametrize("attempt_id", ["../escape", "/tmp/escape", "bad/id", ""])
def test_volume_destination_rejects_unsafe_attempt_id(attempt_id):
    with pytest.raises(ValueError, match="attempt_id"):
        volume_destination(attempt_id, Path("voice.wav"))
