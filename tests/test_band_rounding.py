import pytest

from ielts_scorer.schemas import DimensionScore, round_band_to_half


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, 0.0),
        (4.24, 4.0),
        (4.25, 4.5),
        (6.74, 6.5),
        (6.75, 7.0),
        (9, 9.0),
    ],
)
def test_round_band_to_half(raw, expected):
    assert round_band_to_half(raw) == expected


def test_band_rejects_out_of_range_values():
    with pytest.raises(ValueError):
        DimensionScore(
            dimension="lexical_resource",
            band=9.5,
            evidence=["outside range"],
            feedback="invalid",
        )
