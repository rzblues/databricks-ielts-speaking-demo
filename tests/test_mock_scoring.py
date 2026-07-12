from ielts_scorer.audio_io import first_attempt, load_segments
from ielts_scorer.features import extract_features
from ielts_scorer.scoring import build_mock_report


def test_mock_scoring_is_deterministic():
    attempt = first_attempt(__import__("pathlib").Path("sample_data"))
    segments = load_segments(__import__("pathlib").Path("sample_data/mock_transcripts.json"), attempt.attempt_id)
    features = extract_features(attempt.attempt_id, segments, duration_sec=attempt.duration_sec)

    first = build_mock_report(attempt, segments, features)
    second = build_mock_report(attempt, segments, features)

    assert first.overall_band == second.overall_band
    assert first.to_scoring_result_record()["attempt_id"] == attempt.attempt_id
    assert "estimated IELTS-style" in first.caveats[0]
