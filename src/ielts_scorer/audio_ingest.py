"""Real audio registration and metadata helpers."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac"}
REAL_ASR_AUDIO_EXTENSIONS = {".wav"}
DEFAULT_VOLUME_PATH = "/Volumes/main/ielts_demo/ielts_audio"
ATTEMPT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True)
class AudioMetadata:
    local_path: Path
    audio_exists: bool
    audio_sha256: str
    audio_size_bytes: int
    audio_format: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_audio_file(path: Path, require_wav_for_real_asr: bool = False) -> AudioMetadata:
    if not path.exists():
        raise FileNotFoundError(f"audio file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"audio path is not a file: {path}")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError(f"unsupported audio extension {suffix}; expected one of {sorted(SUPPORTED_AUDIO_EXTENSIONS)}")
    if require_wav_for_real_asr and suffix not in REAL_ASR_AUDIO_EXTENSIONS:
        raise ValueError("real ASR v0 requires .wav input; convert the file before running real ASR")
    size = path.stat().st_size
    if size <= 0:
        raise ValueError(f"audio file is empty: {path}")
    return AudioMetadata(
        local_path=path,
        audio_exists=True,
        audio_sha256=sha256_file(path),
        audio_size_bytes=size,
        audio_format=suffix.removeprefix("."),
    )


def guard_real_audio_required(audio_path: Path, real_audio_required: bool, asr_provider: str) -> None:
    if not real_audio_required:
        return
    if asr_provider == "mock":
        raise ValueError("REAL_AUDIO_REQUIRED=true forbids ASR_PROVIDER=mock")
    validate_audio_file(audio_path, require_wav_for_real_asr=True)


def validate_attempt_id(attempt_id: str) -> str:
    if not ATTEMPT_ID_PATTERN.fullmatch(attempt_id):
        raise ValueError("attempt_id must be 1-128 letters, numbers, dots, underscores, or hyphens")
    return attempt_id


def volume_destination(attempt_id: str, local_path: Path, volume_path: str = DEFAULT_VOLUME_PATH) -> str:
    safe_name = f"{validate_attempt_id(attempt_id)}{local_path.suffix.lower()}"
    return f"{volume_path.rstrip('/')}/{safe_name}"


def upload_to_databricks_volume(local_path: Path, destination_path: str) -> str:
    dbfs_destination = f"dbfs:{destination_path}" if destination_path.startswith("/Volumes/") else destination_path
    completed = subprocess.run(
        ["databricks", "fs", "cp", str(local_path), dbfs_destination, "--overwrite"],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"failed to upload audio to Databricks Volume: {detail}")
    return destination_path


def real_audio_required_from_env() -> bool:
    return os.getenv("REAL_AUDIO_REQUIRED", "false").strip().lower() in {"1", "true", "yes", "on"}
