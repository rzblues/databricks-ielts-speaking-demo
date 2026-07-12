"""LLM scoring client boundary."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod

from ielts_scorer.schemas import ASRSegment, Attempt, ScoringReport, SpeechFeatures
from ielts_scorer.scoring import build_mock_report


class LLMScoringClient(ABC):
    @abstractmethod
    def score(self, attempt: Attempt, segments: list[ASRSegment], features: SpeechFeatures) -> ScoringReport:
        raise NotImplementedError


class MockLLMScoringClient(LLMScoringClient):
    def score(self, attempt: Attempt, segments: list[ASRSegment], features: SpeechFeatures) -> ScoringReport:
        return build_mock_report(attempt, segments, features)


class DatabricksModelServingClient(LLMScoringClient):
    """Optional Databricks serving client using environment configuration."""

    def __init__(self, endpoint_name: str | None = None):
        self.endpoint_name = endpoint_name or os.getenv("DATABRICKS_MODEL_ENDPOINT", "")
        if not self.endpoint_name:
            raise ValueError("DATABRICKS_MODEL_ENDPOINT is required for DatabricksModelServingClient")

    def score(self, attempt: Attempt, segments: list[ASRSegment], features: SpeechFeatures) -> ScoringReport:
        try:
            from databricks.sdk import WorkspaceClient  # type: ignore
        except ImportError as exc:
            raise RuntimeError("install databricks-sdk to use DatabricksModelServingClient") from exc

        client = WorkspaceClient()
        payload = {
            "attempt": attempt.model_dump(mode="json"),
            "segments": [segment.model_dump(mode="json") for segment in segments],
            "features": features.model_dump(mode="json"),
        }
        response = client.serving_endpoints.query(name=self.endpoint_name, inputs=[payload])
        raw = getattr(response, "predictions", response)
        candidate = raw[0] if isinstance(raw, list) else raw
        if isinstance(candidate, str):
            candidate = json.loads(candidate)
        return ScoringReport.model_validate(candidate)


def scoring_client_from_env() -> LLMScoringClient:
    if os.getenv("MOCK_LLM", "true").lower() in {"1", "true", "yes", "on"}:
        return MockLLMScoringClient()
    return DatabricksModelServingClient()
