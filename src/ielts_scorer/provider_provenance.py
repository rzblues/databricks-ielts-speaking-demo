"""Provider provenance for honest demo reporting."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProviderProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audio_source: str = Field(min_length=1)
    asr_provider: str = Field(min_length=1)
    asr_is_mock: bool
    scoring_provider: str = Field(min_length=1)
    scoring_is_mock: bool
    pipeline_mode: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_real_audio_required(self) -> "ProviderProvenance":
        if self.pipeline_mode == "real_audio" and self.audio_source == "mock":
            raise ValueError("real_audio pipeline cannot use mock audio source")
        provider_is_mock = "mock" in self.asr_provider.strip().lower()
        if provider_is_mock != self.asr_is_mock:
            raise ValueError("asr_provider and asr_is_mock must describe the same provider type")
        if self.pipeline_mode == "real_audio" and self.asr_is_mock:
            raise ValueError("real_audio pipeline cannot use mock ASR")
        return self


def mock_demo_provenance() -> ProviderProvenance:
    return ProviderProvenance(
        audio_source="mock",
        asr_provider="mock",
        asr_is_mock=True,
        scoring_provider="rule_based_mock",
        scoring_is_mock=True,
        pipeline_mode="mock_demo",
    )


def registered_real_audio_provenance(
    asr_provider: str = "pending",
    asr_is_mock: bool = False,
    scoring_provider: str = "pending",
    scoring_is_mock: bool = True,
) -> ProviderProvenance:
    return ProviderProvenance(
        audio_source="real_audio",
        asr_provider=asr_provider,
        asr_is_mock=asr_is_mock,
        scoring_provider=scoring_provider,
        scoring_is_mock=scoring_is_mock,
        pipeline_mode="real_audio",
    )
