"""Local sample data loading helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import TypeAdapter

from ielts_scorer.schemas import ASRSegment, Attempt

T = TypeVar("T")


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_attempts(path: Path) -> list[Attempt]:
    return TypeAdapter(list[Attempt]).validate_python(load_json(path))


def load_segments(path: Path, attempt_id: str | None = None) -> list[ASRSegment]:
    segments = TypeAdapter(list[ASRSegment]).validate_python(load_json(path))
    if attempt_id is None:
        return segments
    return [segment for segment in segments if segment.attempt_id == attempt_id]


def first_attempt(sample_dir: Path) -> Attempt:
    attempts = load_attempts(sample_dir / "mock_attempts.json")
    if not attempts:
        raise ValueError("sample_data/mock_attempts.json contains no attempts")
    return attempts[0]
