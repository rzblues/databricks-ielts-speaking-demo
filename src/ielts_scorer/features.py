"""Explainable speech and language feature extraction."""

from __future__ import annotations

import math
import re
from statistics import mean

from ielts_scorer.schemas import ASRSegment, SpeechFeatures

WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
SENTENCE_RE = re.compile(r"[.!?]+")
SINGLE_FILLERS = {"um", "uh", "er", "erm", "ah", "like", "well"}
PHRASE_FILLERS = ("you know", "i mean", "sort of", "kind of")
COMPLEX_MARKERS = {
    "although",
    "because",
    "while",
    "whereas",
    "which",
    "that",
    "when",
    "if",
    "unless",
    "however",
}


def tokenize_words(text: str) -> list[str]:
    return [match.group(0).lower() for match in WORD_RE.finditer(text)]


def transcript_text(segments: list[ASRSegment]) -> str:
    return " ".join(segment.text.strip() for segment in segments if segment.text.strip())


def count_fillers(text: str, words: list[str]) -> int:
    lowered = f" {text.lower()} "
    phrase_count = sum(lowered.count(f" {phrase} ") for phrase in PHRASE_FILLERS)
    single_count = sum(1 for word in words if word in SINGLE_FILLERS)
    return phrase_count + single_count


def count_repetitions(words: list[str]) -> int:
    repetitions = 0
    previous = None
    for word in words:
        if word == previous:
            repetitions += 1
        previous = word
    return repetitions


def avg_asr_confidence(segments: list[ASRSegment]) -> float:
    if not segments:
        return 0.0
    scores = []
    for segment in segments:
        if segment.avg_logprob is None:
            base = 0.75
        else:
            base = max(0.0, min(1.0, math.exp(segment.avg_logprob)))
        no_speech = segment.no_speech_prob if segment.no_speech_prob is not None else 0.0
        scores.append(max(0.0, min(1.0, base * (1.0 - no_speech))))
    return round(mean(scores), 4)


def extract_features(
    attempt_id: str,
    segments: list[ASRSegment],
    duration_sec: float | None = None,
    pause_threshold_sec: float = 0.35,
    long_pause_threshold_sec: float = 1.0,
) -> SpeechFeatures:
    ordered = sorted(segments, key=lambda item: (item.start_sec, item.segment_id))
    inferred_duration = max((segment.end_sec for segment in ordered), default=0.0)
    duration = max(float(duration_sec if duration_sec is not None else inferred_duration), inferred_duration)
    speaking = sum(max(0.0, segment.end_sec - segment.start_sec) for segment in ordered)
    speaking = min(speaking, duration) if duration else speaking
    pauses = [
        max(0.0, current.start_sec - previous.end_sec)
        for previous, current in zip(ordered, ordered[1:])
        if current.start_sec - previous.end_sec >= pause_threshold_sec
    ]

    text = transcript_text(ordered)
    words = tokenize_words(text)
    words_count = len(words)
    sentence_chunks = [chunk.strip() for chunk in SENTENCE_RE.split(text) if chunk.strip()]
    sentence_lengths = [len(tokenize_words(chunk)) for chunk in sentence_chunks]
    complex_sentences = [
        chunk for chunk in sentence_chunks if any(marker in tokenize_words(chunk) for marker in COMPLEX_MARKERS)
    ]

    silence_ratio = 0.0
    if duration > 0:
        silence_ratio = max(0.0, min(1.0, (duration - speaking) / duration))

    filler_count = count_fillers(text, words)
    return SpeechFeatures(
        attempt_id=attempt_id,
        duration_sec=round(duration, 3),
        speaking_sec=round(speaking, 3),
        silence_ratio=round(silence_ratio, 4),
        words_count=words_count,
        words_per_min=round((words_count / duration) * 60, 3) if duration > 0 else 0.0,
        pause_count=len(pauses),
        long_pause_count=sum(1 for pause in pauses if pause >= long_pause_threshold_sec),
        avg_pause_sec=round(mean(pauses), 3) if pauses else 0.0,
        filler_count=filler_count,
        filler_ratio=round(filler_count / words_count, 4) if words_count else 0.0,
        repetition_count=count_repetitions(words),
        lexical_diversity=round(len(set(words)) / words_count, 4) if words_count else 0.0,
        avg_sentence_len=round(mean(sentence_lengths), 3) if sentence_lengths else 0.0,
        complex_sentence_proxy=round(len(complex_sentences) / len(sentence_chunks), 4) if sentence_chunks else 0.0,
        asr_confidence_proxy=avg_asr_confidence(ordered),
    )
