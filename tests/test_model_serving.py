import pytest
from pydantic import ValidationError

from ielts_scorer.features import extract_features
from ielts_scorer.model_serving import build_model_serving_report, score_with_model_serving
from ielts_scorer.provider_provenance import ProviderProvenance
from ielts_scorer.schemas import ASRSegment, Attempt


def bundle():
    attempt = Attempt(
        attempt_id="real-1",
        candidate_id="candidate-1",
        question_id="question-1",
        question_text="Describe a problem you solved.",
        audio_path="/Volumes/main/ielts_demo/ielts_audio/real-1.wav",
        audio_format="wav",
        duration_sec=12,
        source="upload",
    )
    segments = [ASRSegment(attempt_id="real-1", segment_id=0, start_sec=0, end_sec=8, text="I solved it carefully.")]
    features = extract_features("real-1", segments, duration_sec=12)
    provenance = ProviderProvenance(
        audio_source="real_audio",
        asr_provider="local_whisper",
        asr_is_mock=False,
        scoring_provider="pending",
        scoring_is_mock=True,
        pipeline_mode="real_audio",
    )
    return attempt, segments, features, provenance


def payload(evidence):
    return {
        "choices": [{"message": {"content": {
            "fc_band": 6,
            "lr_band": 6,
            "gra_band": 6,
            "p_band": 6,
            "confidence": 0.8,
            "feedback": {
                "fluency_and_coherence": "Clear.",
                "lexical_resource": "Adequate.",
                "grammatical_range_and_accuracy": "Controlled.",
                "pronunciation_intelligibility": "Intelligible.",
            },
            "evidence": evidence,
        }}}],
    }


def test_model_report_preserves_real_asr_provenance():
    attempt, segments, features, provenance = bundle()
    evidence = {name: ["short evidence"] for name in (
        "fluency_and_coherence", "lexical_resource", "grammatical_range_and_accuracy", "pronunciation_intelligibility"
    )}

    report = build_model_serving_report(attempt, segments, features, "endpoint", payload(evidence), provenance)

    assert report.provenance.asr_provider == "local_whisper"
    assert report.provenance.asr_is_mock is False
    assert report.provenance.scoring_provider == "databricks_model_serving:endpoint"


def test_model_report_rejects_string_evidence_instead_of_splitting_characters():
    attempt, segments, features, provenance = bundle()
    evidence = {name: ["short evidence"] for name in (
        "fluency_and_coherence", "lexical_resource", "grammatical_range_and_accuracy", "pronunciation_intelligibility"
    )}
    evidence["fluency_and_coherence"] = "not a list"

    with pytest.raises((ValidationError, ValueError), match="evidence"):
        build_model_serving_report(attempt, segments, features, "endpoint", payload(evidence), provenance)


def test_score_with_model_serving_returns_real_scoring_provenance():
    attempt, segments, features, provenance = bundle()
    evidence = {name: ["short evidence"] for name in (
        "fluency_and_coherence", "lexical_resource", "grammatical_range_and_accuracy", "pronunciation_intelligibility"
    )}
    calls = []

    report = score_with_model_serving(
        attempt,
        segments,
        features,
        "endpoint",
        provenance,
        invoker=lambda endpoint, messages, max_tokens: calls.append((endpoint, messages, max_tokens)) or payload(evidence),
    )

    assert len(calls) == 1
    assert report.provenance.scoring_provider == "databricks_model_serving:endpoint"
    assert report.provenance.scoring_is_mock is False
