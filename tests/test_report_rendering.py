from pathlib import Path

from ielts_scorer.audio_io import first_attempt, load_segments
from ielts_scorer.features import extract_features
from ielts_scorer.report import render_markdown_report
from ielts_scorer.scoring import build_mock_report


def test_report_contains_scores_transcript_features_and_caveat():
    sample_dir = Path("sample_data")
    attempt = first_attempt(sample_dir)
    segments = load_segments(sample_dir / "mock_transcripts.json", attempt.attempt_id)
    features = extract_features(attempt.attempt_id, segments, duration_sec=attempt.duration_sec)
    report = build_mock_report(attempt, segments, features)
    markdown = render_markdown_report(report)

    assert "Overall estimated IELTS-style band score" in markdown
    assert "Pronunciation / intelligibility estimate" in markdown
    assert "## Transcript" in markdown
    assert "## Extracted Features" in markdown
    assert "official IELTS score" not in markdown.lower()
