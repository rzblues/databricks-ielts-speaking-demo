"""Local and Databricks capability probe for Loop 0.

The script performs read-only checks and avoids printing secrets.
"""

from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class CommandResult:
    name: str
    available: bool
    detail: str


def run_command(name: str, args: list[str], timeout_sec: int = 30) -> CommandResult:
    if shutil.which(args[0]) is None:
        return CommandResult(name=name, available=False, detail=f"{args[0]} not found")

    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(name=name, available=False, detail="command timed out")

    output = (completed.stdout or completed.stderr or "").strip()
    first_line = output.splitlines()[0] if output else "no output"
    if completed.returncode != 0:
        return CommandResult(
            name=name,
            available=False,
            detail=f"exit {completed.returncode}: {first_line}",
        )
    return CommandResult(name=name, available=True, detail=first_line)


def has_module(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False


def main() -> int:
    checks = [
        run_command("databricks_cli_version", ["databricks", "--version"]),
        run_command("databricks_current_user", ["databricks", "current-user", "me", "-o", "json"]),
        run_command("databricks_catalogs", ["databricks", "catalogs", "list", "-o", "json"]),
        run_command("databricks_warehouses", ["databricks", "warehouses", "list", "-o", "json"]),
        run_command("databricks_serving_endpoints", ["databricks", "serving-endpoints", "list", "-o", "json"]),
        run_command("databricks_bundle_version", ["databricks", "bundle", "--help"]),
    ]

    print(f"python: {sys.version.split()[0]}")
    print(f"platform: {platform.platform()}")
    print(f"databricks_sdk_module: {'available' if has_module('databricks.sdk') else 'unavailable'}")
    for check in checks:
        status = "ok" if check.available else "failed"
        print(f"{check.name}: {status} - {check.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
