import pytest

from prepare_lora_kit.steps.upscale.review_tiers import REVIEW_TIER_PX, tier_for


@pytest.mark.parametrize(
    ("min_side", "expected"),
    [
        (0, (0, 255)),
        (255, (0, 255)),
        (256, (256, 511)),
        (511, (256, 511)),
        (3071, (2816, 3071)),
    ],
)
def test_tier_for_boundaries(min_side, expected):
    assert tier_for(min_side) == expected


def test_tier_for_unknown_size_has_no_tier():
    assert tier_for(None) is None


def test_tier_width_is_256():
    assert REVIEW_TIER_PX == 256
