"""Validated data contracts for the IELTS Speaking demo."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ielts_scorer.provider_provenance import ProviderProvenance, mock_demo_provenance


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def round_band_to_half(value: float) -> float:
    """Round an IELTS-style band to the nearest 0.5 without banker rounding."""
    if not isinstance(value, (int, float)) or math.isnan(float(value)):
        raise ValueError("band must be a number")
    numeric = float(value)
    if numeric < 0 or numeric > 9:
        raise ValueError("band must be between 0 and 9")
    return math.floor(numeric * 2 + 0.5) / 2


class DemoModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Attempt(DemoModel):
    attempt_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    question_text: str = Field(min_length=1)
    audio_path: str = Field(min_length=1)
    audio_format: str = Field(min_length=1)
    duration_sec: float = Field(ge=0)
    source: Literal["sample", "upload", "databricks", "local"] = "sample"
    created_at: datetime = Field(default_factory=utc_now)


class ASRSegment(DemoModel):
    attempt_id: str = Field(min_length=1)
    segment_id: int = Field(ge=0)
    start_sec: float = Field(ge=0)
    end_sec: float = Field(ge=0)
    text: str
    avg_logprob: float | None = None
    no_speech_prob: float | None = Field(default=None, ge=0, le=1)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_time_order(self) -> "ASRSegment":
        if self.end_sec < self.start_sec:
            raise ValueError("end_sec must be greater than or equal to start_sec")
        return self


class SpeechFeatures(DemoModel):
    attempt_id: str = Field(min_length=1)
    duration_sec: float = Field(ge=0)
    speaking_sec: float = Field(ge=0)
    silence_ratio: float = Field(ge=0, le=1)
    words_count: int = Field(ge=0)
    words_per_min: float = Field(ge=0)
    pause_count: int = Field(ge=0)
    long_pause_count: int = Field(ge=0)
    avg_pause_sec: float = Field(ge=0)
    filler_count: int = Field(ge=0)
    filler_ratio: float = Field(ge=0)
    repetition_count: int = Field(ge=0)
    lexical_diversity: float = Field(ge=0, le=1)
    avg_sentence_len: float = Field(ge=0)
    complex_sentence_proxy: float = Field(ge=0, le=1)
    asr_confidence_proxy: float = Field(ge=0, le=1)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_duration_consistency(self) -> "SpeechFeatures":
        if self.speaking_sec > self.duration_sec and self.duration_sec > 0:
            raise ValueError("speaking_sec cannot exceed duration_sec")
        return self


class DimensionScore(DemoModel):
    dimension: Literal[
        "fluency_and_coherence",
        "lexical_resource",
        "grammatical_range_and_accuracy",
        "pronunciation_intelligibility",
    ]
    band: float
    evidence: list[str] = Field(min_length=1)
    feedback: str = Field(min_length=1)

    @field_validator("band")
    @classmethod
    def normalize_band(cls, value: float) -> float:
        return round_band_to_half(value)


class ScoringReport(DemoModel):
    attempt_id: str = Field(min_length=1)
    overall_band: float
    fc_band: float
    lr_band: float
    gra_band: float
    p_band: float
    confidence: float = Field(ge=0, le=1)
    dimensions: dict[str, DimensionScore]
    transcript: str
    features: SpeechFeatures
    provenance: ProviderProvenance = Field(default_factory=mock_demo_provenance)
    caveats: list[str] = Field(min_length=1)
    model_endpoint: str = Field(min_length=1)
    rubric_version: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("overall_band", "fc_band", "lr_band", "gra_band", "p_band")
    @classmethod
    def normalize_bands(cls, value: float) -> float:
        return round_band_to_half(value)

    @model_validator(mode="after")
    def validate_dimensions(self) -> "ScoringReport":
        expected = {
            "fluency_and_coherence": self.fc_band,
            "lexical_resource": self.lr_band,
            "grammatical_range_and_accuracy": self.gra_band,
            "pronunciation_intelligibility": self.p_band,
        }
        if set(self.dimensions) != set(expected):
            raise ValueError("dimensions must include exactly the four IELTS-style dimensions")
        for name, band in expected.items():
            if self.dimensions[name].dimension != name:
                raise ValueError(f"dimension name does not match key {name}")
            if self.dimensions[name].band != band:
                raise ValueError(f"dimension {name} band does not match top-level band")
        expected_overall = round_band_to_half(sum(expected.values()) / len(expected))
        if self.overall_band != expected_overall:
            raise ValueError("overall_band must equal the rounded average of the four dimension bands")
        if self.features.attempt_id != self.attempt_id:
            raise ValueError("features attempt_id must match report attempt_id")
        if not any("estimated" in caveat.lower() for caveat in self.caveats):
            raise ValueError("report caveats must state that this is estimated")
        return self

    def to_scoring_result_record(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "overall_band": self.overall_band,
            "fc_band": self.fc_band,
            "lr_band": self.lr_band,
            "gra_band": self.gra_band,
            "p_band": self.p_band,
            "confidence": self.confidence,
            "json_report": self.model_dump_json(),
            "model_endpoint": self.model_endpoint,
            "rubric_version": self.rubric_version,
            "audio_source": self.provenance.audio_source,
            "asr_provider": self.provenance.asr_provider,
            "asr_is_mock": self.provenance.asr_is_mock,
            "scoring_provider": self.provenance.scoring_provider,
            "scoring_is_mock": self.provenance.scoring_is_mock,
            "pipeline_mode": self.provenance.pipeline_mode,
            "created_at": self.created_at,
        }
