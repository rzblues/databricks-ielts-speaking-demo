import pytest

from ielts_scorer.provider_provenance import ProviderProvenance, mock_demo_provenance


def test_mock_demo_provenance_is_explicit():
    provenance = mock_demo_provenance()

    assert provenance.asr_is_mock is True
    assert provenance.scoring_is_mock is True
    assert provenance.pipeline_mode == "mock_demo"


def test_real_audio_pipeline_rejects_mock_audio_source():
    with pytest.raises(ValueError):
        ProviderProvenance(
            audio_source="mock",
            asr_provider="local_whisper",
            asr_is_mock=False,
            scoring_provider="mock",
            scoring_is_mock=True,
            pipeline_mode="real_audio",
        )


def test_real_audio_pipeline_rejects_mock_asr():
    with pytest.raises(ValueError, match="mock ASR"):
        ProviderProvenance(
            audio_source="real_audio",
            asr_provider="mock",
            asr_is_mock=True,
            scoring_provider="rule_based_mock",
            scoring_is_mock=True,
            pipeline_mode="real_audio",
        )


def test_provider_mock_flag_must_match_provider_name():
    with pytest.raises(ValueError, match="asr_provider"):
        ProviderProvenance(
            audio_source="real_audio",
            asr_provider="mock",
            asr_is_mock=False,
            scoring_provider="rule_based_mock",
            scoring_is_mock=True,
            pipeline_mode="real_audio",
        )
