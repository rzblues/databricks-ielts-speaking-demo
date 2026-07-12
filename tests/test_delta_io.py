from ielts_scorer.delta_io import LocalDeltaStore


def test_local_delta_store_round_trip(tmp_path):
    store = LocalDeltaStore(tmp_path)
    record = {
        "attempt_id": "a1",
        "candidate_id": "c1",
        "question_id": "q1",
        "question_text": "Describe a city.",
        "audio_path": "sample.wav",
        "audio_format": "wav",
        "duration_sec": 12.0,
        "source": "sample",
        "created_at": "2026-07-02T00:00:00Z",
    }

    store.write_records("attempts", [record])

    assert store.read_records("attempts") == [record]
