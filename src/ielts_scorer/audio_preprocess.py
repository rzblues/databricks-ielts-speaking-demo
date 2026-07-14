"""Audio metadata and preprocessing for real-ASR inputs."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AudioInspection:
    path: Path
    duration_sec: float
    sample_rate_hz: int
    channels: int
    format: str
    size_bytes: int


def inspect_wav(path: Path) -> AudioInspection:
    if not path.exists():
        raise FileNotFoundError(f"audio file does not exist: {path}")
    if path.suffix.lower() != ".wav":
        raise ValueError("WAV metadata extraction requires a .wav file")
    with wave.open(str(path), "rb") as handle:
        sample_rate = handle.getframerate()
        frames = handle.getnframes()
        channels = handle.getnchannels()
        duration = frames / sample_rate if sample_rate else 0.0
    return AudioInspection(
        path=path,
        duration_sec=round(duration, 3),
        sample_rate_hz=sample_rate,
        channels=channels,
        format="wav",
        size_bytes=path.stat().st_size,
    )


def inspect_audio(path: Path) -> AudioInspection:
    if path.suffix.lower() == ".wav":
        return inspect_wav(path)
    if shutil.which("ffprobe") is None:
        raise ValueError("non-WAV metadata requires ffprobe; install ffmpeg or provide WAV")
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=sample_rate,channels:format=duration,format_name",
            "-of",
            "json",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        raise ValueError(completed.stderr.strip() or "ffprobe could not inspect audio")
    payload = json.loads(completed.stdout)
    stream = (payload.get("streams") or [{}])[0]
    fmt = payload.get("format") or {}
    return AudioInspection(
        path=path,
        duration_sec=round(float(fmt.get("duration") or 0), 3),
        sample_rate_hz=int(stream.get("sample_rate") or 0),
        channels=int(stream.get("channels") or 0),
        format=str(fmt.get("format_name") or path.suffix.lower().removeprefix(".")),
        size_bytes=path.stat().st_size,
    )


def ensure_ffmpeg_on_path() -> str:
    existing = shutil.which("ffmpeg")
    if existing:
        return existing
    try:
        from imageio_ffmpeg import get_ffmpeg_exe  # type: ignore
    except ImportError as exc:
        raise RuntimeError("ffmpeg is required to normalize audio to mono 16k WAV") from exc

    bundled = Path(get_ffmpeg_exe())
    if not bundled.is_file():
        raise RuntimeError("bundled ffmpeg executable is unavailable")
    bin_dir = Path("/tmp/ielts_scorer_bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    executable = bin_dir / "ffmpeg"
    if not executable.exists():
        executable.symlink_to(bundled)
    os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
    return str(executable)


def preprocess_for_asr(path: Path, output_dir: Path) -> Path:
    """Return a mono 16k WAV copy for ASR, preserving the original audio."""
    if not path.exists():
        raise FileNotFoundError(f"audio file does not exist: {path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{path.stem}.mono16k.wav"
    inspection = inspect_wav(path) if path.suffix.lower() == ".wav" else None
    if inspection and inspection.channels == 1 and inspection.sample_rate_hz == 16000:
        if path.resolve() != target.resolve():
            target.write_bytes(path.read_bytes())
        return target
    ffmpeg = ensure_ffmpeg_on_path()
    completed = subprocess.run(
        [ffmpeg, "-y", "-i", str(path), "-ac", "1", "-ar", "16000", str(target)],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffmpeg failed to preprocess audio")
    return target
