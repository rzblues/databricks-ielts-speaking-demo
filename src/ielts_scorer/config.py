"""Configuration boundary for the demo."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class DemoConfig:
    mock_asr: bool = True
    mock_llm: bool = True
    local_demo: bool = True
    databricks_demo: bool = False
    sample_data_dir: Path = Path("sample_data")
    output_dir: Path = Path("outputs")

    @classmethod
    def from_env(cls) -> "DemoConfig":
        return cls(
            mock_asr=env_flag("MOCK_ASR", True),
            mock_llm=env_flag("MOCK_LLM", True),
            local_demo=env_flag("LOCAL_DEMO", True),
            databricks_demo=env_flag("DATABRICKS_DEMO", False),
            sample_data_dir=Path(os.getenv("SAMPLE_DATA_DIR", "sample_data")),
            output_dir=Path(os.getenv("OUTPUT_DIR", "outputs")),
        )
