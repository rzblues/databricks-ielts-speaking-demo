import pytest
from pydantic import ValidationError

from ielts_scorer.features import extract_features
from ielts_scorer.schemas import ASRSegment, Attempt, ScoringReport
from ielts_scorer.scoring import build_mock_report


def test_package_imports():
    import ielts_scorer

    assert ielts_scorer.__version__ == "0.1.0"


def test_valid_mock_report_passes_validation():
    attempt = Attempt(
        attempt_id="a1",
        candidate_id="c1",
        question_id="q1",
        question_text="Describe a city you like.",
        audio_path="sample_data/audio.wav",
        audio_format="wav",
        duration_sec=12,
    )
    segments = [
        ASRSegment(
            attempt_id="a1",
            segment_id=0,
            start_sec=0,
            end_sec=6,
            text="I like this city because it is convenient.",
            avg_logprob=-0.2,
            no_speech_prob=0.03,
        )
    ]
    features = extract_features("a1", segments, duration_sec=12)
    report = build_mock_report(attempt, segments, features)

    assert ScoringReport.model_validate(report.model_dump()).attempt_id == "a1"
    assert report.overall_band in {4.5, 5.0, 5.5, 6.0, 6.5, 7.0}


def test_invalid_json_fails_validation():
    with pytest.raises(ValidationError):
        Attempt.model_validate({"attempt_id": "", "duration_sec": -1})


def test_report_rejects_overall_band_that_does_not_match_dimension_average():
    attempt = Attempt(
        attempt_id="a1",
        candidate_id="c1",
        question_id="q1",
        question_text="Describe a city you like.",
        audio_path="sample_data/audio.wav",
        audio_format="wav",
        duration_sec=12,
    )
    segments = [
        ASRSegment(
            attempt_id="a1",
            segment_id=0,
            start_sec=0,
            end_sec=6,
            text="I like this city because it is convenient.",
        )
    ]
    report = build_mock_report(attempt, segments, extract_features("a1", segments, duration_sec=12))

    with pytest.raises(ValidationError, match="overall_band"):
        ScoringReport.model_validate({**report.model_dump(), "overall_band": 9.0})


def test_report_rejects_mismatched_dimension_name():
    attempt = Attempt(
        attempt_id="a1",
        candidate_id="c1",
        question_id="q1",
        question_text="Describe a city you like.",
        audio_path="sample_data/audio.wav",
        audio_format="wav",
        duration_sec=12,
    )
    segments = [ASRSegment(attempt_id="a1", segment_id=0, start_sec=0, end_sec=6, text="A response.")]
    report = build_mock_report(attempt, segments, extract_features("a1", segments, duration_sec=12))
    payload = report.model_dump()
    payload["dimensions"]["fluency_and_coherence"]["dimension"] = "lexical_resource"

    with pytest.raises(ValidationError, match="dimension name"):
        ScoringReport.model_validate(payload)
