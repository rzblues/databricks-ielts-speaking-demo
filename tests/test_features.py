from ielts_scorer.features import extract_features
from ielts_scorer.schemas import ASRSegment


def segment(segment_id, start, end, text, avg_logprob=-0.2, no_speech_prob=0.05):
    return ASRSegment(
        attempt_id="a1",
        segment_id=segment_id,
        start_sec=start,
        end_sec=end,
        text=text,
        avg_logprob=avg_logprob,
        no_speech_prob=no_speech_prob,
    )


def test_extract_features_for_filler_and_repetition_heavy_answer():
    features = extract_features(
        "a1",
        [
            segment(0, 0.0, 4.0, "Um I I like this city because it is safe."),
            segment(1, 5.2, 8.0, "You know it is very very convenient."),
        ],
        duration_sec=10.0,
    )

    assert features.words_count == 17
    assert features.pause_count == 1
    assert features.long_pause_count == 1
    assert features.filler_count == 3
    assert features.repetition_count == 2
    assert features.lexical_diversity < 1
    assert features.complex_sentence_proxy > 0
    assert 0 < features.asr_confidence_proxy <= 1


def test_extract_features_empty_transcript():
    features = extract_features("empty", [], duration_sec=0)

    assert features.words_count == 0
    assert features.words_per_min == 0
    assert features.silence_ratio == 0
    assert features.asr_confidence_proxy == 0


def test_extract_features_one_very_short_segment():
    features = extract_features("a1", [segment(0, 0.0, 0.2, "Hi")], duration_sec=0.2)

    assert features.words_count == 1
    assert features.words_per_min == 300
    assert features.pause_count == 0
