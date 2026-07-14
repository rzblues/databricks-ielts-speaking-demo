"""Streamlit app for the IELTS Speaking demo.

The module imports without Streamlit so tests and Databricks jobs can smoke check it.
"""

from __future__ import annotations

import json
import os
import hashlib
import time
from collections.abc import Callable
from datetime import datetime, timezone
from functools import lru_cache
from html import escape
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from ielts_scorer.asr import LocalWhisperASRClient
from ielts_scorer.audio_preprocess import inspect_audio, preprocess_for_asr
from ielts_scorer.audio_ingest import validate_attempt_id, volume_destination
from ielts_scorer.audio_io import first_attempt, load_segments
from ielts_scorer.features import extract_features
from ielts_scorer.provider_provenance import registered_real_audio_provenance
from ielts_scorer.scoring import build_mock_report
from ielts_scorer.schemas import ScoringReport
from ielts_scorer.schemas import Attempt


def load_sample_report(path: Path | None = None) -> ScoringReport:
    report_path = path or Path(os.getenv("REPORT_JSON", "outputs/attempt_sample_001_report.json"))
    if not report_path.exists():
        raise FileNotFoundError(
            f"{report_path} does not exist. Run `python scripts/run_mock_demo.py` first."
        )
    return ScoringReport.model_validate(json.loads(report_path.read_text(encoding="utf-8")))


def build_embedded_sample_report() -> ScoringReport:
    sample_dir = Path("sample_data")
    attempt = first_attempt(sample_dir)
    segments = load_segments(sample_dir / "mock_transcripts.json", attempt.attempt_id)
    features = extract_features(attempt.attempt_id, segments, duration_sec=attempt.duration_sec)
    return build_mock_report(attempt, segments, features)


def load_databricks_report(attempt_id: str | None = None) -> ScoringReport:
    namespace = os.getenv("DATABRICKS_NAMESPACE", "main.ielts_demo")
    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID", "77cea25dcd8171c6")
    escaped_attempt_id = attempt_id.replace("'", "''") if attempt_id else ""
    where = f"WHERE attempt_id = '{escaped_attempt_id}'" if attempt_id else ""
    query = f"SELECT json_report FROM {namespace}.scoring_results {where} ORDER BY created_at DESC LIMIT 1"

    sdk_error = None
    try:
        from databricks.sdk import WorkspaceClient  # type: ignore

        client = WorkspaceClient()
        response = client.statement_execution.execute_statement(
            statement=query,
            warehouse_id=warehouse_id,
            wait_timeout="30s",
        )
        data_array = statement_data_array(response)
        if data_array:
            return ScoringReport.model_validate_json(data_array[0][0])
        raise FileNotFoundError("No scoring report found in Databricks scoring_results.")
    except FileNotFoundError:
        raise
    except Exception as exc:
        sdk_error = exc

    try:
        from databricks import sql  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            f"Databricks SDK query failed ({sdk_error}); install databricks-sql-connector to try token-based SQL fallback."
        ) from exc

    server_hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME")
    http_path = os.getenv("DATABRICKS_HTTP_PATH")
    access_token = os.getenv("DATABRICKS_TOKEN")
    if not server_hostname or not http_path or not access_token:
        raise RuntimeError(
            f"Databricks SDK report query failed: {sdk_error}. "
            "No explicit token-based SQL fallback is configured."
        )

    where = "WHERE attempt_id = ?" if attempt_id else ""
    params = [attempt_id] if attempt_id else []
    query = f"SELECT json_report FROM {namespace}.scoring_results {where} ORDER BY created_at DESC LIMIT 1"
    with sql.connect(server_hostname=server_hostname, http_path=http_path, access_token=access_token) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
    if row is None:
        raise FileNotFoundError("No scoring report found in Databricks scoring_results.")
    return ScoringReport.model_validate_json(row[0])


def execute_databricks_statement(statement: str):
    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID", "77cea25dcd8171c6")
    return workspace_client().statement_execution.execute_statement(
        statement=statement,
        warehouse_id=warehouse_id,
        wait_timeout="30s",
    )


@lru_cache(maxsize=1)
def workspace_client():
    from databricks.sdk import WorkspaceClient  # type: ignore

    return WorkspaceClient()


@lru_cache(maxsize=4)
def whisper_client(model_name: str) -> LocalWhisperASRClient:
    return LocalWhisperASRClient(model_name=model_name)


def statement_data_array(
    response,
    fetch_statement=None,
    sleep=time.sleep,
    timeout_seconds: float = 90,
) -> list[list]:
    fetch = fetch_statement or workspace_client().statement_execution.get_statement
    deadline = time.monotonic() + timeout_seconds
    while True:
        result = getattr(response, "result", None)
        data_array = getattr(result, "data_array", None) if result is not None else None
        if data_array:
            return data_array

        status = getattr(response, "status", None)
        raw_state = getattr(status, "state", "") if status is not None else ""
        state = str(getattr(raw_state, "value", raw_state) or "").upper().rsplit(".", 1)[-1]
        if state in {"FAILED", "CANCELED", "CLOSED"}:
            error = getattr(status, "error", None)
            message = getattr(error, "message", None) or str(error or state)
            raise RuntimeError(f"Databricks SQL statement {state.lower()}: {message}")
        if state == "SUCCEEDED":
            return []

        statement_id = getattr(response, "statement_id", None)
        if not statement_id:
            return []
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Databricks SQL statement {statement_id} did not finish within {timeout_seconds:.0f} seconds."
            )
        sleep(1)
        response = fetch(statement_id)


def load_platform_summary(attempt_id: str) -> dict:
    namespace = os.getenv("DATABRICKS_NAMESPACE", "main.ielts_demo")
    summary = {"errors": {}}
    try:
        attempt_rows = statement_data_array(
            execute_databricks_statement(
                f"""
                SELECT candidate_id, question_id, question_text, audio_path
                FROM {namespace}.attempts
                WHERE attempt_id = {sql_literal(attempt_id)}
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
        )
        if attempt_rows:
            summary["attempt"] = {
                "candidate_id": attempt_rows[0][0],
                "question_id": attempt_rows[0][1],
                "question_text": attempt_rows[0][2],
                "audio_path": attempt_rows[0][3],
            }
    except Exception as exc:
        summary["errors"]["attempt"] = str(exc)
    try:
        scoring_rows = statement_data_array(
            execute_databricks_statement(
                f"""
                SELECT scoring_provider, scoring_is_mock, model_endpoint
                FROM {namespace}.scoring_results
                WHERE attempt_id = {sql_literal(attempt_id)}
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
        )
        if scoring_rows:
            summary["scoring"] = {
                "provider": scoring_rows[0][0],
                "is_mock": scoring_rows[0][1],
                "endpoint": scoring_rows[0][2],
            }
    except Exception as exc:
        summary["errors"]["scoring"] = str(exc)
    try:
        ai_rows = statement_data_array(
            execute_databricks_statement(
                f"""
                SELECT sentiment, delivery_label, provider
                FROM {namespace}.ai_function_insights
                WHERE attempt_id = {sql_literal(attempt_id)}
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
        )
        if ai_rows:
            summary["sql_ai"] = {"sentiment": ai_rows[0][0], "delivery_label": ai_rows[0][1], "provider": ai_rows[0][2]}
    except Exception as exc:
        summary["errors"]["sql_ai"] = str(exc)
    try:
        quality_rows = statement_data_array(
            execute_databricks_statement(
                f"""
                SELECT status, count(*)
                FROM (
                  SELECT status, row_number() OVER (PARTITION BY check_name ORDER BY check_time DESC) AS row_num
                  FROM {namespace}.quality_check_results
                ) latest
                WHERE row_num = 1
                GROUP BY status
                """
            )
        )
        if quality_rows:
            summary["quality"] = {row[0]: int(row[1]) for row in quality_rows}
    except Exception as exc:
        summary["errors"]["quality"] = str(exc)
    return summary


def sql_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, datetime):
        return f"TIMESTAMP '{value.strftime('%Y-%m-%d %H:%M:%S')}'"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def register_uploaded_audio(
    uploaded_file,
    attempt_id: str,
    candidate_id: str,
    question_id: str,
    question_text: str,
    run_id: str | None = None,
    volume_uploader: Callable | None = None,
) -> str:
    namespace = os.getenv("DATABRICKS_NAMESPACE", "main.ielts_demo")
    volume_path = os.getenv("DATABRICKS_VOLUME_PATH", "/Volumes/main/ielts_demo/ielts_audio")
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in {".wav", ".mp3", ".m4a", ".flac"}:
        raise ValueError("Upload a .wav, .mp3, .m4a, or .flac file.")
    validate_attempt_id(attempt_id)
    if not candidate_id.strip() or not question_id.strip() or not question_text.strip():
        raise ValueError("Candidate ID, question ID, and question are required.")
    audio_path = volume_destination(attempt_id, Path(uploaded_file.name), volume_path)
    content = uploaded_file.getvalue()
    if not content:
        raise ValueError("Uploaded file is empty.")
    max_bytes = int(os.getenv("MAX_AUDIO_UPLOAD_BYTES", str(50 * 1024 * 1024)))
    if len(content) > max_bytes:
        raise ValueError(f"Uploaded file exceeds the {max_bytes // (1024 * 1024)} MB limit.")
    upload_volume_bytes(audio_path, content, uploader=volume_uploader)
    now = datetime.now(timezone.utc)
    execute_databricks_statement(f"DELETE FROM {namespace}.attempts WHERE attempt_id = {sql_literal(attempt_id)}")
    execute_databricks_statement(
        f"""
        INSERT INTO {namespace}.attempts
        (attempt_id, candidate_id, question_id, question_text, audio_path, audio_format, duration_sec, source, created_at)
        VALUES ({sql_literal(attempt_id)}, {sql_literal(candidate_id)}, {sql_literal(question_id)}, {sql_literal(question_text)},
                {sql_literal(audio_path)}, {sql_literal(suffix.removeprefix('.'))}, 0.0, 'upload', {sql_literal(now)})
        """
    )
    execute_databricks_statement(
        f"""
        INSERT INTO {namespace}.processing_runs
        (run_id, attempt_id, pipeline_mode, audio_path, audio_exists, audio_sha256, audio_size_bytes,
         asr_provider, asr_is_mock, scoring_provider, scoring_is_mock, processing_status, error_message, created_at)
        VALUES ({sql_literal(run_id or 'run_' + uuid4().hex)}, {sql_literal(attempt_id)}, 'real_audio', {sql_literal(audio_path)},
                TRUE, {sql_literal(hashlib.sha256(content).hexdigest())}, {len(content)}, 'pending', FALSE, 'pending', TRUE, 'UPLOADED', '', {sql_literal(now)})
        """
    )
    return audio_path


def upload_volume_bytes(
    destination_path: str,
    content: bytes,
    uploader: Callable | None = None,
) -> None:
    upload = uploader or workspace_client().files.upload
    try:
        upload(destination_path, BytesIO(content), overwrite=True)
    except Exception as exc:
        raise RuntimeError("Audio could not be uploaded to the Databricks Volume.") from exc


def insert_row(table: str, columns: list[str], values: list) -> None:
    namespace = os.getenv("DATABRICKS_NAMESPACE", "main.ielts_demo")
    execute_databricks_statement(
        f"INSERT INTO {namespace}.{table} ({', '.join(columns)}) "
        f"VALUES ({', '.join(sql_literal(value) for value in values)})"
    )


def process_uploaded_audio_on_databricks_compute(
    uploaded_file,
    attempt_id: str,
    candidate_id: str,
    question_id: str,
    question_text: str,
    progress: Callable[[str, int], None] | None = None,
) -> ScoringReport:
    namespace = os.getenv("DATABRICKS_NAMESPACE", "main.ielts_demo")
    run_id = "run_" + uuid4().hex
    notify = progress or (lambda _message, _percent: None)
    notify("Uploading audio to the governed Volume", 10)
    audio_path = register_uploaded_audio(uploaded_file, attempt_id, candidate_id, question_id, question_text, run_id=run_id)
    try:
        notify("Preparing a local ASR working copy", 28)
        with TemporaryDirectory(prefix=f"ielts_{attempt_id}_") as work_dir:
            local_audio = Path(work_dir) / Path(audio_path).name
            local_audio.write_bytes(uploaded_file.getvalue())
            processed_audio = preprocess_for_asr(local_audio, Path(work_dir) / "processed")
            duration_sec = inspect_audio(processed_audio).duration_sec
            attempt = Attempt(
                attempt_id=attempt_id,
                candidate_id=candidate_id,
                question_id=question_id,
                question_text=question_text,
                audio_path=audio_path,
                audio_format=local_audio.suffix.lower().removeprefix("."),
                duration_sec=duration_sec,
                source="upload",
            )
            asr_attempt = attempt.model_copy(update={"audio_path": str(processed_audio)})
            notify("Loading Whisper on Databricks App compute", 42)
            configured_model = os.getenv(
                "WHISPER_MODEL",
                "/Volumes/main/ielts_demo/ielts_audio/models/tiny.en.pt",
            )
            model_name = str(materialize_volume_file(configured_model))
            notify("Transcribing real audio with Whisper", 58)
            segments = [
                segment
                for segment in whisper_client(model_name).transcribe(asr_attempt)
                if segment.text.strip()
            ]
        if not segments:
            raise ValueError("real ASR returned empty transcript")
        notify("Extracting explainable speech features", 76)
        features = extract_features(attempt_id, segments, duration_sec=duration_sec)
        provenance = registered_real_audio_provenance(
            asr_provider="databricks_app_local_whisper",
            asr_is_mock=False,
            scoring_provider="rule_based_mock",
            scoring_is_mock=True,
        )
        report = build_mock_report(attempt, segments, features, provenance=provenance)
    except Exception as exc:
        execute_databricks_statement(
            f"UPDATE {namespace}.processing_runs SET processing_status = 'FAILED', error_message = {sql_literal(str(exc)[:1000])} "
            f"WHERE run_id = {sql_literal(run_id)}"
        )
        raise

    notify("Writing assessment records to Delta", 88)
    execute_databricks_statement(f"DELETE FROM {namespace}.asr_segments WHERE attempt_id = {sql_literal(attempt_id)}")
    execute_databricks_statement(f"DELETE FROM {namespace}.speech_features WHERE attempt_id = {sql_literal(attempt_id)}")
    execute_databricks_statement(f"DELETE FROM {namespace}.scoring_results WHERE attempt_id = {sql_literal(attempt_id)}")

    segment_columns = ["attempt_id", "segment_id", "start_sec", "end_sec", "text", "avg_logprob", "no_speech_prob", "created_at"]
    segment_values = []
    for segment in segments:
        values = [segment.attempt_id, segment.segment_id, segment.start_sec, segment.end_sec, segment.text, segment.avg_logprob, segment.no_speech_prob, segment.created_at]
        segment_values.append("(" + ", ".join(sql_literal(value) for value in values) + ")")
    execute_databricks_statement(
        f"INSERT INTO {namespace}.asr_segments ({', '.join(segment_columns)}) VALUES {', '.join(segment_values)}"
    )
    insert_row(
        "speech_features",
        [
            "attempt_id",
            "duration_sec",
            "speaking_sec",
            "silence_ratio",
            "words_count",
            "words_per_min",
            "pause_count",
            "long_pause_count",
            "avg_pause_sec",
            "filler_count",
            "filler_ratio",
            "repetition_count",
            "lexical_diversity",
            "avg_sentence_len",
            "complex_sentence_proxy",
            "asr_confidence_proxy",
            "created_at",
        ],
        [
            features.attempt_id,
            features.duration_sec,
            features.speaking_sec,
            features.silence_ratio,
            features.words_count,
            features.words_per_min,
            features.pause_count,
            features.long_pause_count,
            features.avg_pause_sec,
            features.filler_count,
            features.filler_ratio,
            features.repetition_count,
            features.lexical_diversity,
            features.avg_sentence_len,
            features.complex_sentence_proxy,
            features.asr_confidence_proxy,
            features.created_at,
        ],
    )
    record = report.to_scoring_result_record()
    insert_row("scoring_results", list(record), [record[column] for column in record])
    execute_databricks_statement(
        f"UPDATE {namespace}.processing_runs SET processing_status = 'COMPLETED', asr_provider = 'databricks_app_local_whisper', "
        f"asr_is_mock = false, scoring_provider = 'rule_based_mock', scoring_is_mock = true WHERE run_id = {sql_literal(run_id)}"
    )
    notify("Assessment ready", 100)
    return report


def load_report() -> tuple[ScoringReport, str | None]:
    if os.getenv("DATABRICKS_DEMO", "true").lower() in {"1", "true", "yes", "on"}:
        try:
            return load_databricks_report(os.getenv("ATTEMPT_ID")), None
        except Exception as exc:
            if os.getenv("ALLOW_LOCAL_REPORT_FALLBACK", "false").lower() not in {"1", "true", "yes", "on"}:
                raise RuntimeError(f"Databricks report load failed in strict demo mode: {exc}") from exc
            return build_embedded_sample_report(), str(exc)
    try:
        return load_sample_report(), None
    except Exception as exc:
        return build_embedded_sample_report(), str(exc)


def download_databricks_file(file_path: str, max_bytes: int) -> bytes:
    try:
        response = workspace_client().files.download(file_path)
        with response.contents as stream:
            content = stream.read(max_bytes + 1)
    except Exception as exc:
        raise RuntimeError("A required file could not be downloaded from the Databricks Volume.") from exc
    return content


def download_volume_file(audio_path: str, max_bytes: int) -> bytes:
    try:
        return download_databricks_file(audio_path, max_bytes)
    except RuntimeError as exc:
        raise RuntimeError("Scored audio could not be downloaded from the Databricks Volume.") from exc


def materialize_volume_file(
    remote_path: str,
    cache_dir: Path = Path("/tmp/ielts_scorer_models"),
    loader: Callable[[str, int], bytes] | None = None,
    max_bytes: int | None = None,
) -> Path:
    path = Path(remote_path)
    if not remote_path.startswith("/Volumes/"):
        return path

    limit = max_bytes or int(os.getenv("MAX_WHISPER_MODEL_BYTES", str(500 * 1024 * 1024)))
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(remote_path.encode("utf-8")).hexdigest()[:12]
    local_path = cache_dir / f"{cache_key}-{path.name}"
    if local_path.is_file() and local_path.stat().st_size > 0:
        return local_path

    content = (loader or download_databricks_file)(remote_path, limit)
    if not content:
        raise ValueError("Whisper model file is empty.")
    if len(content) > limit:
        raise ValueError(f"Whisper model exceeds the {limit // (1024 * 1024)} MB cache limit.")
    temporary_path = local_path.with_suffix(local_path.suffix + ".tmp")
    temporary_path.write_bytes(content)
    temporary_path.replace(local_path)
    return local_path


def load_audio_playback_payload(
    audio_path: str | Path,
    volume_loader: Callable[[str], bytes] | None = None,
) -> tuple[bytes, str, str]:
    path = Path(audio_path)
    mime_types = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
    }
    mime_type = mime_types.get(path.suffix.lower())
    if mime_type is None:
        raise ValueError("Audio playback supports WAV, MP3, M4A, and FLAC files.")
    max_bytes = int(os.getenv("MAX_AUDIO_PLAYBACK_BYTES", str(50 * 1024 * 1024)))
    if path.is_file():
        if path.stat().st_size > max_bytes:
            raise ValueError(f"Scored audio exceeds the {max_bytes // (1024 * 1024)} MB playback limit.")
        content = path.read_bytes()
    elif str(path).startswith("/Volumes/"):
        loader = volume_loader or (lambda remote_path: download_volume_file(remote_path, max_bytes))
        content = loader(str(path))
    else:
        raise FileNotFoundError(f"Scored audio file is unavailable: {path.name}")
    if len(content) > max_bytes:
        raise ValueError(f"Scored audio exceeds the {max_bytes // (1024 * 1024)} MB playback limit.")
    if not content:
        raise ValueError("Scored audio file is empty.")
    return content, mime_type, path.name


def databricks_theme_css() -> str:
    return """
    <style>
    :root {
        --db-red: #ff3621;
        --db-red-hover: #d92b18;
        --db-red-soft: #fff0ed;
        --db-bg: #f7f7f5;
        --db-surface: #ffffff;
        --db-sidebar: #fbfaf8;
        --db-border: #e2e3e1;
        --db-border-strong: #c9cbc8;
        --db-text: #1f2328;
        --db-muted: #687076;
        --db-subtle: #92989d;
        --db-green: #16865c;
        --db-amber: #a96800;
        --db-error: #c7382b;
        --db-radius-sm: 4px;
        --db-radius-md: 6px;
        --db-radius-lg: 8px;
        --db-shadow: none;
    }

    html, body, [class*="css"] {
        font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: var(--db-text);
        letter-spacing: 0;
        -webkit-font-smoothing: antialiased;
    }

    [data-testid="stAppViewContainer"] {
        background: var(--db-surface);
    }

    [data-testid="stHeader"] {
        background: transparent;
        height: 2.5rem;
    }

    [data-testid="stMain"] .block-container {
        max-width: 1480px;
        padding: 0.5rem 2rem 2rem;
    }

    [data-testid="stSidebar"] {
        background: var(--db-surface);
        border-right: 1px solid var(--db-border);
        width: 264px !important;
    }

    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        padding: 1rem 1rem 2rem;
    }

    [data-testid="stSidebar"] hr {
        border-color: var(--db-border);
        margin: 1rem 0;
    }

    [data-testid="stFileUploaderDropzone"] {
        background: var(--db-surface);
        border: 1px dashed var(--db-border-strong);
        border-radius: var(--db-radius-md);
        padding: 0.75rem;
    }

    [data-testid="stFileUploaderDropzone"] button {
        border-radius: var(--db-radius-md);
    }

    [data-testid="stFileUploaderDropzoneInstructions"],
    [data-testid="stFileUploaderDropzoneInstructions"] p,
    [data-testid="stFileUploaderDropzoneInstructions"] span,
    [data-testid="stFileUploaderDropzoneInstructions"] small {
        color: var(--db-muted) !important;
    }

    [data-stale="true"] {
        opacity: 1 !important;
    }

    [data-testid="stStatusWidget"] {
        background: var(--db-surface);
        border: 1px solid var(--db-border);
        border-left: 3px solid var(--db-red);
        border-radius: var(--db-radius-md);
        color: var(--db-text);
    }

    [data-testid="stProgress"] > div > div > div > div {
        background-color: var(--db-red);
    }

    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea {
        background: var(--db-surface);
        border: 1px solid var(--db-border);
        border-radius: var(--db-radius-sm);
        box-shadow: none;
        color: var(--db-text);
        font-size: 13px;
    }

    [data-testid="stSidebar"] [data-testid="stTextArea"] textarea {
        min-height: 74px;
    }

    [data-testid="stTextInput"] input:focus,
    [data-testid="stTextArea"] textarea:focus {
        border-color: var(--db-red);
        box-shadow: 0 0 0 3px rgba(255, 54, 33, 0.12);
    }

    [data-testid="stWidgetLabel"] p {
        color: var(--db-muted);
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
    }

    .stButton > button {
        width: 100%;
        min-height: 36px;
        border: 1px solid var(--db-border-strong);
        border-radius: var(--db-radius-md);
        background: var(--db-surface);
        color: var(--db-text);
        box-shadow: var(--db-shadow);
        font-size: 13px;
        font-weight: 650;
    }

    .stButton > button:hover {
        border-color: var(--db-text);
        color: var(--db-text);
    }

    .stButton > button[kind="primary"] {
        border-color: var(--db-red);
        background: var(--db-red);
        color: #ffffff;
    }

    .stButton > button[kind="primary"]:hover {
        border-color: var(--db-red-hover);
        background: var(--db-red-hover);
        color: #ffffff;
    }

    .stButton > button:disabled,
    .stButton > button[kind="primary"]:disabled {
        border-color: var(--db-border);
        background: var(--db-surface);
        color: var(--db-subtle);
        box-shadow: none;
        opacity: 1;
    }

    .section-label,
    .rail-section-label {
        color: var(--db-red);
        font-size: 11px;
        font-weight: 750;
        text-transform: uppercase;
        letter-spacing: 0;
    }

    .app-header {
        margin-bottom: 12px;
    }

    .app-title {
        margin: 0 0 3px;
        padding: 0;
        color: var(--db-text);
        font-size: 23px;
        font-weight: 780;
        line-height: 1.25;
        letter-spacing: 0;
    }

    .app-subtitle {
        margin: 0;
        color: var(--db-muted);
        font-size: 12.5px;
        line-height: 1.55;
    }

    .rail-marker {
        display: flex;
        align-items: center;
        gap: 9px;
        margin-bottom: 5px;
    }

    .rail-marker-dot {
        width: 13px;
        height: 13px;
        flex: 0 0 13px;
        border-radius: 2px;
        background: var(--db-red);
    }

    .rail-marker-title {
        color: var(--db-text);
        font-size: 14px;
        font-weight: 750;
    }

    .rail-tagline {
        margin: 0 0 18px;
        color: var(--db-muted);
        font-size: 11.5px;
        line-height: 1.45;
    }

    .rail-section-label {
        margin: 0 0 8px;
    }

    .rail-provenance-item {
        display: flex;
        align-items: center;
        gap: 7px;
        margin: 8px 0;
        color: var(--db-muted);
        font-size: 11.5px;
        line-height: 1.35;
    }

    .rail-provenance-dot {
        width: 7px;
        height: 7px;
        flex: 0 0 7px;
        border-radius: 50%;
        background: var(--db-green);
    }

    .rail-provenance-dot.mock {
        background: var(--db-amber);
    }

    .top-bar {
        display: flex;
        align-items: center;
        min-height: 72px;
        margin-bottom: 12px;
        padding: 11px 14px 11px 16px;
        background: var(--db-surface);
        border: 1px solid var(--db-border);
        border-left: 3px solid var(--db-red);
        border-radius: var(--db-radius-lg);
        box-shadow: var(--db-shadow);
    }

    .top-bar-overall {
        display: flex;
        flex-direction: column;
        min-width: 88px;
    }

    .top-bar-overall-value {
        color: var(--db-text);
        font-size: 31px;
        font-weight: 790;
        line-height: 1;
        letter-spacing: 0;
    }

    .top-bar-overall-label {
        margin-top: 5px;
        color: var(--db-muted);
        font-size: 9.5px;
        font-weight: 750;
        letter-spacing: 0;
    }

    .top-bar-divider {
        align-self: stretch;
        width: 1px;
        margin: 0 16px;
        background: var(--db-border);
    }

    .top-bar-dims {
        display: grid;
        grid-template-columns: repeat(4, minmax(48px, auto));
        gap: 7px 16px;
        color: var(--db-muted);
        font-size: 11px;
        white-space: nowrap;
    }

    .top-bar-dims b {
        color: var(--db-text);
        font-size: 13px;
        font-variant-numeric: tabular-nums;
    }

    .top-bar-status {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: 7px 13px;
        margin-left: auto;
        padding-left: 18px;
    }

    .top-bar-status-item {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        color: var(--db-muted);
        font-size: 10.5px;
        font-weight: 650;
        white-space: nowrap;
    }

    .status-dot {
        width: 7px;
        height: 7px;
        flex: 0 0 7px;
        border-radius: 50%;
        background: var(--db-green);
    }

    .status-dot.mock {
        background: var(--db-amber);
    }

    .demo-pill {
        padding: 4px 7px;
        background: var(--db-sidebar);
        border: 1px solid var(--db-border);
        border-radius: var(--db-radius-sm);
        color: var(--db-muted);
        font-size: 9px;
        font-weight: 750;
        letter-spacing: 0;
    }

    .workspace-grid {
        display: grid;
        grid-template-columns: minmax(0, 1.55fr) minmax(360px, 0.9fr);
        gap: 14px;
        align-items: start;
    }

    .workspace-column {
        display: flex;
        flex-direction: column;
        gap: 14px;
        min-width: 0;
    }

    .report-card {
        overflow: hidden;
        background: var(--db-surface);
        border: 1px solid var(--db-border);
        border-radius: var(--db-radius-lg);
        box-shadow: var(--db-shadow);
    }

    .report-card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        padding: 12px 15px;
        border-bottom: 1px solid var(--db-border);
    }

    .report-card-title {
        margin-top: 3px;
        color: var(--db-text);
        font-size: 14px;
        font-weight: 730;
    }

    .report-meta {
        color: var(--db-subtle);
        font-size: 11.5px;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }

    .transcript-body {
        padding: 14px 16px;
        color: var(--db-text);
        font-size: 13.5px;
        line-height: 1.7;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--db-surface);
        border-color: var(--db-border);
        border-radius: var(--db-radius-lg);
        box-shadow: var(--db-shadow);
    }

    .audio-player-title {
        margin-top: 3px;
        color: var(--db-text);
        font-size: 13.5px;
        font-weight: 730;
    }

    .audio-player-meta {
        margin-top: 3px;
        color: var(--db-subtle);
        font-size: 11.5px;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }

    [data-testid="stAudio"] audio {
        width: 100%;
        height: 42px;
    }

    .question-context {
        margin-bottom: 10px;
        padding: 8px 10px;
        background: var(--db-bg);
        border-left: 2px solid var(--db-red);
        color: var(--db-muted);
        font-size: 12.5px;
    }

    .dimension-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
    }

    .dimension-card {
        min-height: 172px;
        padding: 13px 15px;
        background: var(--db-surface);
        border: 1px solid var(--db-border);
        border-radius: var(--db-radius-lg);
        box-shadow: var(--db-shadow);
    }

    .dimension-heading {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 9px;
    }

    .dimension-name {
        color: var(--db-text);
        font-size: 13px;
        font-weight: 730;
        line-height: 1.35;
    }

    .dimension-band {
        color: var(--db-red);
        font-size: 17px;
        font-weight: 780;
    }

    .dimension-evidence {
        margin: 0 0 11px;
        padding: 0;
        list-style: none;
    }

    .dimension-evidence li {
        margin: 4px 0;
        color: var(--db-muted);
        font-size: 11.5px;
        line-height: 1.45;
    }

    .dimension-evidence li::before {
        content: "";
        display: inline-block;
        width: 4px;
        height: 4px;
        margin: 0 7px 2px 0;
        border-radius: 50%;
        background: var(--db-subtle);
    }

    .dimension-feedback {
        margin: 0;
        padding-top: 10px;
        border-top: 1px solid var(--db-border);
        color: var(--db-text);
        font-size: 12px;
        line-height: 1.5;
    }

    .feature-list {
        padding: 2px 15px;
    }

    .feature-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        min-height: 34px;
        border-bottom: 1px solid var(--db-border);
    }

    .feature-row:last-child {
        border-bottom: 0;
    }

    .feature-row-label {
        color: var(--db-muted);
        font-size: 11.5px;
        font-weight: 550;
    }

    .feature-row-value {
        color: var(--db-text);
        font-size: 12px;
        font-weight: 720;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
    }

    .privacy-note {
        margin-top: 14px;
        padding: 12px 14px;
        background: var(--db-surface);
        border: 1px solid var(--db-border);
        border-radius: var(--db-radius-md);
        color: var(--db-muted);
        font-size: 11.5px;
        line-height: 1.55;
    }

    [data-testid="stAlert"] {
        border-radius: var(--db-radius-md);
    }

    [data-testid="stExpander"] {
        border-color: var(--db-border);
        border-radius: var(--db-radius-md);
    }
    </style>
    """


def top_bar_markup(report: ScoringReport, platform_summary: dict) -> str:
    scores = [
        ("FC", report.fc_band),
        ("LR", report.lr_band),
        ("GRA", report.gra_band),
        ("P", report.p_band),
    ]
    dimensions = "".join(
        f"<span>{escape(label)}&nbsp;<b>{value:.1f}</b></span>"
        for label, value in scores
    )
    provenance = report.provenance
    audio_mock = provenance.audio_source != "real_audio"
    audio_label = "Real audio" if provenance.audio_source == "real_audio" else "Mock audio"
    asr_label = "Mock ASR" if provenance.asr_is_mock else f"Real ASR · {provenance.asr_provider}"
    scoring_label = (
        "Mock scoring"
        if provenance.scoring_is_mock
        else f"Real scoring · {provenance.scoring_provider}"
    )
    scoring = platform_summary.get("scoring", {})
    sql_ai = platform_summary.get("sql_ai", {})
    quality = platform_summary.get("quality", {})
    model_endpoint = scoring.get("endpoint") or report.model_endpoint or provenance.scoring_provider
    sql_label = sql_ai.get("delivery_label") or "Pending"
    sql_sentiment = sql_ai.get("sentiment") or ""
    quality_pass = quality.get("PASS", 0)
    quality_fail = quality.get("FAIL", 0)
    statuses = [
        (audio_label, audio_mock),
        (asr_label, provenance.asr_is_mock),
        (scoring_label, provenance.scoring_is_mock),
        (f"Model Serving · {model_endpoint}", provenance.scoring_is_mock),
        (f"SQL AI: {sql_label}" + (f" · {sql_sentiment}" if sql_sentiment else ""), False),
        (f"Quality: {quality_pass} pass / {quality_fail} fail", quality_fail > 0),
    ]
    items = "".join(
        f'<span class="top-bar-status-item"><span class="status-dot{" mock" if is_mock else ""}"></span>'
        f"{escape(str(label))}</span>"
        for label, is_mock in statuses
    )
    return (
        '<div class="top-bar" data-testid="db-top-bar">'
        '<div class="top-bar-overall">'
        f'<span class="top-bar-overall-value">{report.overall_band:.1f}</span>'
        '<span class="top-bar-overall-label">OVERALL BAND</span></div>'
        '<div class="top-bar-divider"></div>'
        f'<div class="top-bar-dims">{dimensions}</div>'
        f'<div class="top-bar-status">{items}<span class="demo-pill">DEMO ESTIMATE</span></div></div>'
    )


def transcript_card_markup(report: ScoringReport, attempt_summary: dict) -> str:
    context = ""
    if attempt_summary:
        question = escape(str(attempt_summary.get("question_text", "")))
        candidate = escape(str(attempt_summary.get("candidate_id", "")))
        question_id = escape(str(attempt_summary.get("question_id", "")))
        context = f'<div class="question-context"><strong>{candidate} · {question_id}</strong><br>{question}</div>'
    return (
        '<section class="report-card">'
        '<div class="report-card-header"><div><div class="section-label">Assessment record</div>'
        '<div class="report-card-title">Transcript</div></div>'
        f'<div class="report-meta">{escape(report.attempt_id)} · {escape(report.provenance.asr_provider)}</div></div>'
        f'<div class="transcript-body">{context}{escape(report.transcript)}</div></section>'
    )


def dimension_grid_markup(report: ScoringReport) -> str:
    labels = {
        "fluency_and_coherence": "Fluency & Coherence",
        "lexical_resource": "Lexical Resource",
        "grammatical_range_and_accuracy": "Grammar Range & Accuracy",
        "pronunciation_intelligibility": "Pronunciation / Intelligibility Estimate",
    }
    cards = []
    for key in labels:
        dimension = report.dimensions[key]
        evidence = "".join(f"<li>{escape(item)}</li>" for item in dimension.evidence)
        cards.append(
            '<article class="dimension-card">'
            '<div class="dimension-heading">'
            f'<div class="dimension-name">{escape(labels[key])}</div>'
            f'<div class="dimension-band">{dimension.band:.1f}</div></div>'
            f'<ul class="dimension-evidence">{evidence}</ul>'
            f'<p class="dimension-feedback">{escape(dimension.feedback)}</p></article>'
        )
    return f'<div class="dimension-grid">{"".join(cards)}</div>'


def feature_table_markup(report: ScoringReport) -> str:
    features = report.features
    feature_items = [
        ("Words per minute", f"{features.words_per_min:.1f}"),
        ("Lexical diversity", f"{features.lexical_diversity:.2f}"),
        ("Filler ratio", f"{features.filler_ratio:.2f}"),
        ("Silence ratio", f"{features.silence_ratio:.2f}"),
        ("Average sentence length", f"{features.avg_sentence_len:.1f}"),
        ("ASR confidence", f"{features.asr_confidence_proxy:.2f}"),
        ("Duration", f"{features.duration_sec:.1f} s"),
        ("Speaking time", f"{features.speaking_sec:.1f} s"),
        ("Word count", str(features.words_count)),
        ("Pause count", str(features.pause_count)),
        ("Long pauses", str(features.long_pause_count)),
        ("Average pause", f"{features.avg_pause_sec:.2f} s"),
        ("Filler count", str(features.filler_count)),
        ("Repetitions", str(features.repetition_count)),
        ("Complex sentence proxy", f"{features.complex_sentence_proxy:.2f}"),
    ]
    rows = "".join(
        '<div class="feature-row">'
        f'<span class="feature-row-label">{escape(label)}</span>'
        f'<span class="feature-row-value">{escape(value)}</span></div>'
        for label, value in feature_items
    )
    return (
        '<section class="report-card"><div class="report-card-header"><div>'
        '<div class="section-label">Explainable signals</div><div class="report-card-title">Extracted features</div>'
        f'</div></div><div class="feature-list">{rows}</div></section>'
    )


def privacy_note_markup(report: ScoringReport) -> str:
    caveats = " ".join(escape(caveat) for caveat in report.caveats)
    return (
        '<div class="privacy-note"><strong>Demo assessment.</strong> '
        f'{caveats} Audio bytes are not stored in Delta tables; only paths and metadata are recorded.</div>'
    )


def render_scored_audio_player(st, report: ScoringReport, attempt_summary: dict) -> None:
    audio_path = attempt_summary.get("audio_path") if attempt_summary else None
    if not audio_path:
        st.caption("Scored audio is unavailable for this attempt.")
        return
    try:
        audio_bytes, mime_type, filename = load_audio_playback_payload(audio_path)
    except (FileNotFoundError, ValueError, OSError, RuntimeError) as exc:
        st.caption(str(exc))
        return
    audio_format = Path(filename).suffix.removeprefix(".").upper()
    with st.container(border=True):
        label_col, player_col = st.columns([0.8, 1.7], gap="small")
        with label_col:
            st.markdown(
                '<div class="section-label">Candidate recording</div>'
                '<div class="audio-player-title">Scored audio</div>'
                f'<div class="audio-player-meta">{report.features.duration_sec:.1f} s · {escape(audio_format)}</div>',
                unsafe_allow_html=True,
            )
        with player_col:
            st.audio(audio_bytes, format=mime_type)


def main() -> None:
    try:
        import streamlit as st
    except ImportError:
        report, warning = load_report()
        if warning:
            print(f"Databricks report warning: {warning}")
        print(f"Overall estimated IELTS-style band score: {report.overall_band:.1f}")
        return

    st.set_page_config(
        page_title="IELTS Speaking Assessment",
        page_icon=":material/graphic_eq:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(databricks_theme_css(), unsafe_allow_html=True)
    st.markdown(
        """
        <header class="app-header">
          <h1 class="app-title">IELTS Speaking Assessment</h1>
          <p class="app-subtitle">Estimated IELTS-style band score · Demo assessment, not a certified IELTS result</p>
        </header>
        """,
        unsafe_allow_html=True,
    )

    load_slot = st.empty()
    with load_slot.container():
        load_status = st.status("Loading assessment data", expanded=True)
        load_progress = st.progress(20, text="Connecting to Databricks SQL")
    try:
        report, report_warning = load_report()
    except Exception as exc:
        load_status.update(label="Assessment data could not be loaded", state="error", expanded=True)
        load_progress.progress(100, text="Databricks report query failed")
        st.error("Databricks report data is unavailable. No sample result is substituted in strict demo mode.")
        with st.expander("Connection diagnostic", expanded=False):
            st.code(str(exc))
        st.stop()
    if report_warning:
        st.warning("Explicit local fallback is enabled, so a built-in sample report is shown.")
        with st.expander("Connection diagnostic", expanded=False):
            st.code(report_warning)

    databricks_demo = os.getenv("DATABRICKS_DEMO", "true").lower() in {"1", "true", "yes", "on"}
    load_progress.progress(65, text="Loading platform provenance and quality checks")
    platform_summary = load_platform_summary(report.attempt_id) if databricks_demo else {}
    attempt_summary = platform_summary.get("attempt", {})
    load_progress.progress(100, text="Assessment ready")
    load_status.update(label="Assessment ready", state="complete", expanded=False)
    load_slot.empty()

    with st.sidebar:
        st.markdown(
            """
            <div class="rail-marker">
              <span class="rail-marker-dot"></span>
              <span class="rail-marker-title">IELTS Speaking Assessment</span>
            </div>
            <p class="rail-tagline">Estimated IELTS-style band score · Demo assessment</p>
            <div class="rail-section-label">Upload &amp; attempt</div>
            """,
            unsafe_allow_html=True,
        )
        uploaded = st.file_uploader(
            "Speaking audio",
            type=["wav", "mp3", "m4a", "flac"],
            help="Accepted formats: WAV, MP3, M4A, and FLAC.",
        )
        attempt_id = st.text_input("Attempt ID", value=os.getenv("ATTEMPT_ID", "attempt_real_app_001"))
        candidate_id = st.text_input("Candidate ID", value="demo_candidate_app")
        question_id = st.text_input("Question ID", value="part2_problem")
        question_text = st.text_area("Question", value="Describe a time you solved a difficult problem.")
        if st.button("Register audio", disabled=uploaded is None, use_container_width=True):
            registration_status = st.status("Registering audio", expanded=True)
            try:
                registration_status.write("Uploading audio to the governed Databricks Volume")
                registered_path = register_uploaded_audio(uploaded, attempt_id, candidate_id, question_id, question_text)
                registration_status.update(label="Audio registered", state="complete", expanded=False)
                st.success(f"Registered: {registered_path}")
                st.info("Audio registered. Continue with Whisper ASR, or use the notebook/job path for longer files.")
            except Exception as exc:
                registration_status.update(label="Audio registration failed", state="error", expanded=True)
                st.error(f"Upload/register failed: {exc}")
        if st.button(
            "Process with Whisper ASR",
            type="primary",
            disabled=uploaded is None,
            use_container_width=True,
        ):
            process_status = st.status("Preparing real-audio assessment", expanded=True)
            process_progress = process_status.progress(5, text="Validating upload")

            def update_processing_status(message: str, percent: int) -> None:
                process_status.update(label=message, state="running", expanded=True)
                process_progress.progress(percent, text=message)

            try:
                processed_report = process_uploaded_audio_on_databricks_compute(
                    uploaded,
                    attempt_id,
                    candidate_id,
                    question_id,
                    question_text,
                    progress=update_processing_status,
                )
                process_status.update(label="Assessment ready", state="complete", expanded=False)
                st.success(f"Processed real ASR attempt: {processed_report.attempt_id}")
                st.rerun()
            except Exception as exc:
                process_status.update(label="Real ASR processing failed", state="error", expanded=True)
                st.error(f"Real ASR processing failed: {exc}")

        st.markdown("<hr />", unsafe_allow_html=True)
        st.markdown('<div class="rail-section-label">Provenance</div>', unsafe_allow_html=True)
        provenance = report.provenance
        provenance_items = [
            ("Real audio" if provenance.audio_source == "real_audio" else "Mock audio", provenance.audio_source != "real_audio"),
            ("Mock ASR" if provenance.asr_is_mock else f"Real ASR · {provenance.asr_provider}", provenance.asr_is_mock),
            ("Mock scoring" if provenance.scoring_is_mock else f"Real scoring · {provenance.scoring_provider}", provenance.scoring_is_mock),
        ]
        st.markdown(
            "".join(
                '<div class="rail-provenance-item">'
                f'<span class="rail-provenance-dot{" mock" if is_mock else ""}"></span>'
                f"{escape(label)}</div>"
                for label, is_mock in provenance_items
            ),
            unsafe_allow_html=True,
        )

    st.markdown(top_bar_markup(report, platform_summary), unsafe_allow_html=True)
    content_cols = st.columns([1.55, 0.9], gap="small")
    with content_cols[0]:
        render_scored_audio_player(st, report, attempt_summary)
        st.markdown(transcript_card_markup(report, attempt_summary), unsafe_allow_html=True)
        st.markdown(
            '<div class="section-label" style="margin: 14px 0 8px;">Evidence &amp; feedback</div>',
            unsafe_allow_html=True,
        )
        st.markdown(dimension_grid_markup(report), unsafe_allow_html=True)
    with content_cols[1]:
        st.markdown(feature_table_markup(report), unsafe_allow_html=True)

    st.markdown(privacy_note_markup(report), unsafe_allow_html=True)


if __name__ == "__main__":
    main()
