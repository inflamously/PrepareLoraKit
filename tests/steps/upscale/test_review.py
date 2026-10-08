from prepare_lora_kit.steps.upscale.review import _review_flagged_decisions


def _item(path, min_side, *, is_jpeg, tier_lo):
    return {
        "path": path, "name": path, "min_side": min_side, "target": 3072,
        "tier_lo": tier_lo, "tier_hi": tier_lo + 255, "is_jpeg": is_jpeg,
        "initial_decision": "upscale",
    }


def _answers(monkeypatch, *answers):
    replies = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(replies))


def test_keep_size_tier_cleans_jpegs_and_skips_others(monkeypatch):
    _answers(monkeypatch, "u", "k")
    decisions = _review_flagged_decisions([
        _item("hi.jpg", 2100, is_jpeg=True, tier_lo=2048),
        _item("hi.png", 2200, is_jpeg=False, tier_lo=2048),
        _item("low.png", 300, is_jpeg=False, tier_lo=256),
    ])

    # Tiers are asked smallest first: low tier upscaled, high tier kept.
    assert decisions == {"low.png": "upscale", "hi.jpg": "cleanup", "hi.png": "skip"}


def test_individual_review_ignores_decisions_that_do_not_apply(monkeypatch):
    _answers(monkeypatch, "i", "c", "u")
    big = _item("big.jpg", 3500, is_jpeg=True, tier_lo=3328)
    big["initial_decision"] = "cleanup"
    png = _item("big.png", 3400, is_jpeg=False, tier_lo=3328)
    png["target"] = 4096

    decisions = _review_flagged_decisions([png, big])

    # Cleanup is JPEG-only and upscale needs min_side < target: both fall back.
    assert decisions == {"big.png": "upscale", "big.jpg": "cleanup"}
