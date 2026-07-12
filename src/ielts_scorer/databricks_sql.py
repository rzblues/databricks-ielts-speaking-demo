"""Small Databricks SQL Statement API helper used by platform scripts."""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime
from typing import Any

WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID", "77cea25dcd8171c6")
NAMESPACE = os.getenv("DATABRICKS_NAMESPACE", "main.ielts_demo")


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, datetime):
        return f"TIMESTAMP '{value.strftime('%Y-%m-%d %H:%M:%S')}'"
    text = str(value).replace("\\", "\\\\").replace("'", "''")
    return "'" + text + "'"


def run_statement(statement: str, warehouse_id: str | None = None, timeout: int = 120) -> dict[str, Any]:
    payload = {
        "warehouse_id": warehouse_id or WAREHOUSE_ID,
        "wait_timeout": "30s",
        "on_wait_timeout": "CONTINUE",
        "statement": statement,
    }
    completed = subprocess.run(
        ["databricks", "api", "post", "/api/2.0/sql/statements", "--json", json.dumps(payload), "-o", "json"],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    response = json.loads(completed.stdout)
    state = response.get("status", {}).get("state")
    deadline = time.monotonic() + timeout
    statement_id = response.get("statement_id")
    while state in {"PENDING", "RUNNING"}:
        if not statement_id:
            raise RuntimeError(f"statement is {state} but response has no statement_id: {response}")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"statement {statement_id} did not finish within {timeout} seconds")
        time.sleep(1)
        completed = subprocess.run(
            ["databricks", "api", "get", f"/api/2.0/sql/statements/{statement_id}", "-o", "json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=max(1, int(deadline - time.monotonic())),
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
        response = json.loads(completed.stdout)
        state = response.get("status", {}).get("state")
    if state != "SUCCEEDED":
        raise RuntimeError(f"statement did not succeed: {state} - {response}")
    return response


def fetch_data_array(statement: str) -> list[list[Any]]:
    response = run_statement(statement)
    return response.get("result", {}).get("data_array", [])


def fetch_one(statement: str) -> list[Any] | None:
    rows = fetch_data_array(statement)
    return rows[0] if rows else None
