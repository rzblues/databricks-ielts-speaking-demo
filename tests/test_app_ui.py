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
    assert (
        '[data-testid="stsidebar"] {\n'
        "        background: var(--db-surface);\n"
        "        border-right: 1px solid var(--db-border);"
    ) in css

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


def test_upload_instructions_and_loading_state_remain_visible_on_white():
    app = load_app_module()

    css = app.databricks_theme_css().lower()

    assert '[data-testid="stfileuploaderdropzoneinstructions"]' in css
    assert "color: var(--db-muted) !important;" in css
    assert '[data-stale="true"]' in css
    assert '[data-testid="ststatuswidget"]' in css
    assert '[data-testid="stfileuploaderfile"]' in css
    assert '[data-testid="stalert"]' in css


def test_uploaded_audio_gets_a_new_safe_attempt_id():
    app = load_app_module()

    attempt_id = app.create_upload_attempt_id(
        "My Speaking Answer.m4a",
        timestamp="20260714_221530",
        nonce="a1b2c3",
    )

    assert attempt_id == "attempt_my_speaking_answer_20260714_221530_a1b2c3"
    assert app.validate_attempt_id(attempt_id) == attempt_id


def test_processing_status_uses_dark_text_on_a_light_surface():
    app = load_app_module()

    markup = app.processing_status_markup("Running Model Serving", 82)
    css = app.databricks_theme_css().lower()

    assert 'class="processing-status running"' in markup
    assert 'style="width: 82%"' in markup
    assert "#ffffff" not in markup.lower()
    assert ".processing-status" in css
    assert "color: var(--db-text) !important;" in css


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


def test_register_uploaded_audio_uses_databricks_files_api(monkeypatch):
    app = load_app_module()
    uploaded_calls = []
    statements = []

    def upload(file_path, contents, *, overwrite):
        uploaded_calls.append((file_path, contents.read(), overwrite))

    monkeypatch.setattr(app, "execute_databricks_statement", statements.append)
    uploaded_file = SimpleNamespace(name="answer.wav", getvalue=lambda: b"RIFF-real-audio")

    audio_path = app.register_uploaded_audio(
        uploaded_file,
        "attempt_upload_001",
        "candidate_001",
        "part2_problem",
        "Describe a difficult problem.",
        volume_uploader=upload,
    )

    assert audio_path == "/Volumes/main/ielts_demo/ielts_audio/attempt_upload_001.wav"
    assert uploaded_calls == [(audio_path, b"RIFF-real-audio", True)]
    assert len(statements) == 3


def test_volume_model_is_materialized_to_writable_cache(tmp_path):
    app = load_app_module()
    remote_path = "/Volumes/main/ielts_demo/ielts_audio/models/tiny.en.pt"
    requested = []

    local_path = app.materialize_volume_file(
        remote_path,
        cache_dir=tmp_path,
        loader=lambda path, limit: requested.append((path, limit)) or b"model-weights",
        max_bytes=100,
    )

    assert requested == [(remote_path, 100)]
    assert local_path.parent == tmp_path
    assert local_path.read_bytes() == b"model-weights"

    app.materialize_volume_file(
        remote_path,
        cache_dir=tmp_path,
        loader=lambda *_: (_ for _ in ()).throw(AssertionError("cache should be reused")),
        max_bytes=100,
    )


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
