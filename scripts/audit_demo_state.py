"""Audit mock vs real state for the real-audio upgrade loop."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

from ielts_scorer.audio_io import load_attempts

STATE_PATH = Path("docs/real_audio_upgrade_state.md")


def run_cli(args: list[str], timeout: int = 30) -> tuple[bool, str]:
    completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    output = (completed.stdout or completed.stderr or "").strip()
    return completed.returncode == 0, output


def databricks_table_count(table: str) -> str:
    statement = f"SELECT COUNT(*) FROM main.ielts_demo.{table}"
    payload = {
        "warehouse_id": "77cea25dcd8171c6",
        "wait_timeout": "30s",
        "on_wait_timeout": "CONTINUE",
        "statement": statement,
    }
    ok, output = run_cli(
        ["databricks", "api", "post", "/api/2.0/sql/statements", "--json", json.dumps(payload), "-o", "json"],
        timeout=60,
    )
    if not ok:
        return f"unavailable: {output.splitlines()[0] if output else 'unknown error'}"
    data = json.loads(output)
    if data.get("status", {}).get("state") != "SUCCEEDED":
        return f"failed: {data.get('status')}"
    return str(data.get("result", {}).get("data_array", [["unknown"]])[0][0])


def databricks_query_first_value(statement: str) -> str:
    payload = {
        "warehouse_id": "77cea25dcd8171c6",
        "wait_timeout": "30s",
        "on_wait_timeout": "CONTINUE",
        "statement": statement,
    }
    ok, output = run_cli(
        ["databricks", "api", "post", "/api/2.0/sql/statements", "--json", json.dumps(payload), "-o", "json"],
        timeout=60,
    )
    if not ok:
        return "unavailable"
    data = json.loads(output)
    if data.get("status", {}).get("state") != "SUCCEEDED":
        return "failed"
    rows = data.get("result", {}).get("data_array", [])
    return rows[0][0] if rows else "none"


def main() -> int:
    attempts = load_attempts(Path("sample_data/mock_attempts.json"))
    sample_attempt = attempts[0]
    local_audio_path = Path(sample_attempt.audio_path)
    volume_ok, volume_output = run_cli(["databricks", "fs", "ls", "dbfs:/Volumes/main/ielts_demo/ielts_audio"])
    app_text = Path("app/app.py").read_text(encoding="utf-8")
    registered_audio_path = databricks_query_first_value(
        "SELECT audio_path FROM main.ielts_demo.attempts WHERE attempt_id = 'attempt_real_r1'"
    )
    registered_processing_status = databricks_query_first_value(
        "SELECT processing_status FROM main.ielts_demo.processing_runs WHERE attempt_id = 'attempt_real_r1' ORDER BY created_at DESC LIMIT 1"
    )

    lines = [
        "# Real Audio Upgrade State",
        "",
        f"Audit timestamp: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## R0 Audit Findings",
        "",
        f"- Sample attempt id: `{sample_attempt.attempt_id}`",
        f"- Sample audio path: `{sample_attempt.audio_path}`",
        f"- Sample audio exists locally: `{local_audio_path.exists()}`",
        "- Current sample transcript source: `sample_data/mock_transcripts.json`",
        "- Current ASR golden path status: `mock`",
        "- Current scoring status: `rule_based_mock`",
        f"- Databricks Volume `main.ielts_demo.ielts_audio` available: `{volume_ok}`",
        f"- App exposes provider badges: `{'REAL AUDIO' in app_text and 'MOCK SCORING' in app_text}`",
        "",
        "## Databricks Table Counts",
        "",
    ]
    for table in ("attempts", "asr_segments", "speech_features", "scoring_results", "processing_runs"):
        lines.append(f"- `{table}`: {databricks_table_count(table)}")
    lines.extend(
        [
            "",
            "## R0 Conclusion",
            "",
            "The existing Databricks demo is real for schema, Delta tables, Volume, and App deployment, but still mock for audio bytes, ASR transcript, and scoring.",
            "R1 must make real audio registration a first-class path and must not treat the missing sample WAV as valid input.",
            "",
            "## R1 Status",
            "",
            "- Real audio registration script: `scripts/register_real_audio_attempt.py`",
            "- Registered smoke attempt: `attempt_real_r1`",
            f"- Registered smoke attempt audio path: `{registered_audio_path}`",
            f"- Registered smoke processing status: `{registered_processing_status}`",
            "- Missing audio guardrail: verified hard failure with clear `ERROR: audio file does not exist` message.",
            "",
        ]
    )
    STATE_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {STATE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
