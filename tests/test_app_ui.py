import importlib.util
import re
from pathlib import Path
from types import SimpleNamespace


def load_app_module():
    spec = importlib.util.spec_from_file_location("ielts_demo_app_ui", Path("app/app.py"))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_databricks_theme_uses_restrained_brand_tokens_without_gradients():
    app = load_app_module()

    css = app.databricks_theme_css().lower()

    assert "#ff3621" in css
    assert "--db-bg" in css
    assert "linear-gradient" not in css
    assert "backdrop-filter" not in css
    assert '[data-testid="stappviewcontainer"] {\n        background: var(--db-surface);' in css
    assert "--db-shadow: none;" in css

    allowed_colors = {
        "#16865c",
        "#1f2328",
        "#687076",
        "#92989d",
        "#a96800",
        "#c7382b",
        "#c9cbc8",
        "#d92b18",
        "#e2e3e1",
        "#f7f7f5",
        "#fbfaf8",
        "#ff3621",
        "#fff0ed",
        "#ffffff",
    }
    assert set(re.findall(r"#[0-9a-f]{6}", css)) <= allowed_colors


def test_score_and_evidence_markup_match_the_2a_information_hierarchy():
    app = load_app_module()
    report = app.build_embedded_sample_report()

    score_markup = app.top_bar_markup(
        report,
        {"scoring": {}, "sql_ai": {}, "quality": {}},
    )
    evidence_markup = app.dimension_grid_markup(report)

    assert "OVERALL BAND" in score_markup
    assert f">{report.overall_band:.1f}<" in score_markup
    assert "Model Serving" in score_markup
    assert "SQL AI" in score_markup
    assert "Quality" in score_markup
    assert "Fluency &amp; Coherence" in evidence_markup
    assert "Lexical Resource" in evidence_markup
    assert "Grammar Range &amp; Accuracy" in evidence_markup
    assert "Pronunciation / Intelligibility Estimate" in evidence_markup


def test_feature_table_is_human_readable_instead_of_raw_json():
    app = load_app_module()
    report = app.build_embedded_sample_report()

    markup = app.feature_table_markup(report)

    assert "Words per minute" in markup
    assert "Lexical diversity" in markup
    assert "ASR confidence" in markup
    assert 'class="feature-list"' in markup
    assert "<table" not in markup
    assert "{\"attempt_id\"" not in markup


def test_audio_playback_payload_reads_the_scored_audio_file():
    app = load_app_module()
    audio_path = Path("sample_data/audio/synthetic_demo.wav")

    audio_bytes, mime_type, filename = app.load_audio_playback_payload(audio_path)

    assert audio_bytes == audio_path.read_bytes()
    assert mime_type == "audio/wav"
    assert filename == "synthetic_demo.wav"


def test_audio_playback_payload_falls_back_to_databricks_files_api():
    app = load_app_module()
    audio_path = "/Volumes/main/ielts_demo/ielts_audio/remote_attempt.wav"
    requested_paths = []

    def volume_loader(path):
        requested_paths.append(path)
        return b"RIFF-remote-audio"

    audio_bytes, mime_type, filename = app.load_audio_playback_payload(
        audio_path,
        volume_loader=volume_loader,
    )

    assert requested_paths == [audio_path]
    assert audio_bytes == b"RIFF-remote-audio"
    assert mime_type == "audio/wav"
    assert filename == "remote_attempt.wav"


def test_statement_data_array_waits_for_a_pending_warehouse_query():
    app = load_app_module()
    pending = SimpleNamespace(
        statement_id="statement-1",
        status=SimpleNamespace(state="PENDING", error=None),
        result=None,
    )
    succeeded = SimpleNamespace(
        statement_id="statement-1",
        status=SimpleNamespace(state="SUCCEEDED", error=None),
        result=SimpleNamespace(data_array=[["report-json"]]),
    )
    fetched = []

    rows = app.statement_data_array(
        pending,
        fetch_statement=lambda statement_id: fetched.append(statement_id) or succeeded,
        sleep=lambda _: None,
        timeout_seconds=1,
    )

    assert rows == [["report-json"]]
    assert fetched == ["statement-1"]
