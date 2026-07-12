import importlib.util
from pathlib import Path


def test_app_module_imports_without_streamlit():
    spec = importlib.util.spec_from_file_location("ielts_demo_app", Path("app/app.py"))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert hasattr(module, "load_sample_report")


def test_app_load_report_fails_closed_without_explicit_fallback(monkeypatch):
    spec = importlib.util.spec_from_file_location("ielts_demo_app_fallback", Path("app/app.py"))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    monkeypatch.setenv("DATABRICKS_DEMO", "true")
    monkeypatch.setenv("ALLOW_LOCAL_REPORT_FALLBACK", "false")
    monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)

    try:
        module.load_report()
    except RuntimeError as exc:
        assert "Databricks report" in str(exc)
    else:
        raise AssertionError("strict Databricks mode must not display an embedded sample")


def test_app_load_report_uses_sample_only_with_explicit_fallback(monkeypatch):
    spec = importlib.util.spec_from_file_location("ielts_demo_app_explicit_fallback", Path("app/app.py"))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    monkeypatch.setenv("DATABRICKS_DEMO", "true")
    monkeypatch.setenv("ALLOW_LOCAL_REPORT_FALLBACK", "true")
    monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)
    report, warning = module.load_report()

    assert report.attempt_id == "attempt_sample_001"
    assert warning is not None
