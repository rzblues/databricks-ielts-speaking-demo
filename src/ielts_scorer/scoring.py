"""Deterministic IELTS-style mock scoring."""

from __future__ import annotations

from ielts_scorer.features import transcript_text
from ielts_scorer.provider_provenance import ProviderProvenance, mock_demo_provenance
from ielts_scorer.schemas import ASRSegment, Attempt, DimensionScore, ScoringReport, SpeechFeatures, round_band_to_half

RUBRIC_VERSION = "ielts-style-demo-v0"
CAVEATS = [
    "This is an estimated IELTS-style band score for demo assessment only.",
    "Pronunciation is represented by a pronunciation / intelligibility estimate, not phoneme-level diagnosis.",
    "Mock scoring is deterministic and should be replaced by a validated model before production use.",
]


def clamp(value: float, low: float = 0.0, high: float = 9.0) -> float:
    return max(low, min(high, value))


def score_fluency(features: SpeechFeatures) -> float:
    score = 5.0
    if 110 <= features.words_per_min <= 170:
        score += 1.2
    elif 80 <= features.words_per_min < 110 or 170 < features.words_per_min <= 190:
        score += 0.5
    else:
        score -= 0.8
    score -= min(1.2, features.silence_ratio * 3.0)
    score -= min(0.8, features.filler_ratio * 5.0)
    score -= min(0.7, features.long_pause_count * 0.25)
    score -= min(0.5, features.repetition_count * 0.08)
    return round_band_to_half(clamp(score))


def score_lexical(features: SpeechFeatures) -> float:
    score = 4.5
    score += min(1.5, features.lexical_diversity * 2.0)
    if features.words_count >= 120:
        score += 1.0
    elif features.words_count >= 60:
        score += 0.5
    score -= min(0.5, features.filler_ratio * 2.0)
    return round_band_to_half(clamp(score))


def score_grammar(features: SpeechFeatures) -> float:
    score = 4.5
    if 8 <= features.avg_sentence_len <= 22:
        score += 0.8
    elif features.avg_sentence_len > 22:
        score += 0.4
    score += min(1.2, features.complex_sentence_proxy * 2.0)
    if features.words_count >= 80:
        score += 0.4
    return round_band_to_half(clamp(score))


def score_pronunciation(features: SpeechFeatures) -> float:
    score = 4.0 + features.asr_confidence_proxy * 2.5
    score -= min(0.8, features.silence_ratio * 1.5)
    score -= min(0.4, features.filler_ratio * 2.0)
    return round_band_to_half(clamp(score))


def build_mock_report(
    attempt: Attempt,
    segments: list[ASRSegment],
    features: SpeechFeatures,
    model_endpoint: str = "mock-local-scorer",
    provenance: ProviderProvenance | None = None,
) -> ScoringReport:
    fc = score_fluency(features)
    lr = score_lexical(features)
    gra = score_grammar(features)
    p = score_pronunciation(features)
    overall = round_band_to_half((fc + lr + gra + p) / 4.0)
    transcript = transcript_text(segments)
    dimensions = {
        "fluency_and_coherence": DimensionScore(
            dimension="fluency_and_coherence",
            band=fc,
            evidence=[
                f"Speech rate: {features.words_per_min:.1f} words/min",
                f"Silence ratio: {features.silence_ratio:.2f}",
                f"Long pauses: {features.long_pause_count}",
            ],
            feedback="Develop answers with steady pacing and clear links between ideas.",
        ),
        "lexical_resource": DimensionScore(
            dimension="lexical_resource",
            band=lr,
            evidence=[
                f"Words: {features.words_count}",
                f"Lexical diversity: {features.lexical_diversity:.2f}",
                f"Filler ratio: {features.filler_ratio:.2f}",
            ],
            feedback="Use more precise topic vocabulary and reduce repeated filler expressions.",
        ),
        "grammatical_range_and_accuracy": DimensionScore(
            dimension="grammatical_range_and_accuracy",
            band=gra,
            evidence=[
                f"Average sentence length: {features.avg_sentence_len:.1f}",
                f"Complex sentence proxy: {features.complex_sentence_proxy:.2f}",
            ],
            feedback="Mix short and complex sentences while keeping grammar controlled.",
        ),
        "pronunciation_intelligibility": DimensionScore(
            dimension="pronunciation_intelligibility",
            band=p,
            evidence=[
                f"ASR confidence proxy: {features.asr_confidence_proxy:.2f}",
                "Pronunciation is inferred from transcript confidence and timing only.",
            ],
            feedback="Focus on intelligibility, word stress, and reducing hesitation that harms clarity.",
        ),
    }
    confidence = min(0.95, max(0.35, 0.5 + features.asr_confidence_proxy * 0.3 + min(features.words_count, 120) / 600))
    return ScoringReport(
        attempt_id=attempt.attempt_id,
        overall_band=overall,
        fc_band=fc,
        lr_band=lr,
        gra_band=gra,
        p_band=p,
        confidence=round(confidence, 3),
        dimensions=dimensions,
        transcript=transcript,
        features=features,
        provenance=provenance or mock_demo_provenance(),
        caveats=CAVEATS,
        model_endpoint=model_endpoint,
        rubric_version=RUBRIC_VERSION,
    )
