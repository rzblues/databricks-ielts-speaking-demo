"""ASR client boundary with mock and real providers."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

from ielts_scorer.audio_io import load_segments
from ielts_scorer.schemas import ASRSegment, Attempt


class ASRClient(ABC):
    @abstractmethod
    def transcribe(self, attempt: Attempt) -> list[ASRSegment]:
        raise NotImplementedError


class MockASRClient(ASRClient):
    def __init__(self, transcript_path: Path = Path("sample_data/mock_transcripts.json")):
        self.transcript_path = transcript_path

    def transcribe(self, attempt: Attempt) -> list[ASRSegment]:
        segments = load_segments(self.transcript_path, attempt.attempt_id)
        if not segments:
            raise ValueError(f"no mock ASR segments found for {attempt.attempt_id}")
        return segments


class LocalWhisperASRClient(ASRClient):
    """Optional local Whisper integration.

    This class is intentionally lazy: importing the package never imports Whisper.
    """

    provider = "local_whisper"

    def __init__(self, model_name: str = "tiny.en"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                import whisper  # type: ignore
            except ImportError as exc:
                raise RuntimeError("install openai-whisper to use LocalWhisperASRClient") from exc
            self._model = whisper.load_model(self.model_name)
        return self._model

    def transcribe(self, attempt: Attempt) -> list[ASRSegment]:
        if not Path(attempt.audio_path).exists():
            raise FileNotFoundError(f"real ASR audio path does not exist locally: {attempt.audio_path}")
        model = self._load_model()
        result = model.transcribe(attempt.audio_path, language="en", fp16=False)
        segments = []
        for index, item in enumerate(result.get("segments", [])):
            segments.append(
                ASRSegment(
                    attempt_id=attempt.attempt_id,
                    segment_id=index,
                    start_sec=float(item.get("start", 0.0)),
                    end_sec=float(item.get("end", 0.0)),
                    text=str(item.get("text", "")).strip(),
                    avg_logprob=item.get("avg_logprob"),
                    no_speech_prob=item.get("no_speech_prob"),
                )
            )
        return segments


WhisperASRClient = LocalWhisperASRClient


def asr_client_from_env() -> ASRClient:
    provider = os.getenv("ASR_PROVIDER", "mock").strip().lower()
    mock_asr = os.getenv("MOCK_ASR", "true").strip().lower() in {"1", "true", "yes", "on"}
    real_audio_required = os.getenv("REAL_AUDIO_REQUIRED", "false").strip().lower() in {"1", "true", "yes", "on"}
    if mock_asr or provider == "mock":
        if real_audio_required:
            raise ValueError("REAL_AUDIO_REQUIRED=true forbids mock ASR")
        return MockASRClient()
    if provider == "local_whisper":
        return LocalWhisperASRClient(model_name=os.getenv("WHISPER_MODEL", "tiny.en"))
    raise ValueError(f"unsupported ASR_PROVIDER={provider}")
