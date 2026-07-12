"""Run the local mock IELTS Speaking demo end to end."""

from __future__ import annotations

from pathlib import Path

from ielts_scorer.audio_io import first_attempt, load_segments
from ielts_scorer.config import DemoConfig
from ielts_scorer.delta_io import LocalDeltaStore
from ielts_scorer.features import extract_features
from ielts_scorer.report import render_markdown_report, write_report_files
from ielts_scorer.scoring import build_mock_report


def run_mock_demo(config: DemoConfig | None = None) -> str:
    config = config or DemoConfig.from_env()
    attempt = first_attempt(config.sample_data_dir)
    segments = load_segments(config.sample_data_dir / "mock_transcripts.json", attempt.attempt_id)
    features = extract_features(attempt.attempt_id, segments, duration_sec=attempt.duration_sec)
    report = build_mock_report(attempt, segments, features)
    json_path, markdown_path = write_report_files(report, config.output_dir)
    local_store = LocalDeltaStore(config.output_dir / "local_tables")
    local_store.write_records("attempts", [attempt.model_dump(mode="json")])
    local_store.write_records("asr_segments", [segment.model_dump(mode="json") for segment in segments])
    local_store.write_records("speech_features", [features.model_dump(mode="json")])
    local_store.write_records("scoring_results", [report.to_scoring_result_record()])
    print(f"attempt_id={attempt.attempt_id}")
    print(f"overall_band={report.overall_band:.1f}")
    print(f"json_report={json_path}")
    print(f"markdown_report={markdown_path}")
    print(f"local_tables={config.output_dir / 'local_tables'}")
    return render_markdown_report(report)


if __name__ == "__main__":
    run_mock_demo()
