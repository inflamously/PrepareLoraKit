"""Tests for caption cleanup — in particular region-label enforcement.

The compose prompt *asks* the model to keep human region labels; these lock down the
check that makes it true regardless of what the model returns.
"""
from pathlib import Path

from prepare_lora_kit.steps.caption_bbox.validation import (
    clean_caption_for_mode,
    enforce_region_labels,
)


def _ann(label):
    return {"x1": 0.1, "y1": 0.1, "x2": 0.4, "y2": 0.4, "label": label}


def test_appends_a_label_the_caption_dropped():
    caption = "A brass telescope on a wooden tripod beside a window"

    result = enforce_region_labels(caption, [_ann("a chipped enamel mug")])

    assert result == caption + ", a chipped enamel mug"


def test_leaves_a_label_the_caption_already_covers():
    caption = "A brass telescope beside a chipped enamel mug"

    assert enforce_region_labels(caption, [_ann("a chipped enamel mug")]) == caption


def test_covered_check_tolerates_different_wording():
    caption = "A brass telescope beside chipped enamel mugs on a shelf"

    # Singular vs plural, reordered — already represented, so nothing is appended.
    assert enforce_region_labels(caption, [_ann("chipped enamel mug")]) == caption


# ── Regression: a paraphrased label must not be re-appended ────────────────────
#
# Compose is asked to weave labels in *naturally*, so it drops modifiers. Treating
# that as a miss appended the full label and produced captions that described the
# same thing twice — generic prose first, the precise label tacked on the end.

def test_a_paraphrased_label_is_not_appended():
    caption = "A brass telescope beside a chipped mug on a wooden shelf"

    result = enforce_region_labels(caption, [_ann("a chipped enamel mug with a blue rim")])

    assert result == caption


def test_a_label_reduced_to_its_bare_head_noun_is_not_appended():
    caption = "A brass telescope beside a mug"

    assert enforce_region_labels(caption, [_ann("a chipped enamel mug")]) == caption


def test_a_genuinely_absent_region_is_still_appended():
    caption = "A brass telescope on a wooden tripod beside a tall window"

    result = enforce_region_labels(caption, [_ann("a chipped mug")])

    assert result == caption + ", a chipped mug"


def test_a_long_label_is_reported_rather_than_appended():
    # Appending a full region caption produces a second, competing description.
    caption = "A brass telescope on a wooden tripod beside a tall window"
    long_label = "a chipped enamel mug with a blue rim resting on a folded newspaper"

    assert enforce_region_labels(caption, [_ann(long_label)]) == caption


def test_qualifiers_do_not_decide_whether_a_region_was_mentioned():
    # The label names a mug, not a rim: a caption mentioning "rim" alone is not it.
    caption = "A brass telescope beside a polished rim"

    result = enforce_region_labels(caption, [_ann("a chipped mug")])

    assert result.endswith(", a chipped mug")


def test_no_annotations_leaves_the_caption_untouched():
    caption = "A brass telescope"

    assert enforce_region_labels(caption, []) == caption
    assert enforce_region_labels(caption, None) == caption


def test_strips_the_concept_token_from_a_label_before_appending():
    # A region captioned in the UI carries the token on its own crop sidecar; the
    # token belongs once, at the head of the caption — not mid-sentence.
    result = enforce_region_labels(
        "A brass telescope", [_ann("tok, a chipped enamel mug")], concept_token="tok",
    )

    assert result == "A brass telescope, a chipped enamel mug"


def test_a_label_that_is_only_the_token_is_ignored():
    caption = "A brass telescope"

    assert enforce_region_labels(caption, [_ann("tok")], concept_token="tok") == caption


def test_enforcement_never_shortens_the_caption():
    caption = "A weathered brass telescope, gold trim, on a tripod"

    result = enforce_region_labels(caption, [_ann("a red curtain"), _ann("gold trim")])

    assert result.startswith(caption)


def test_clean_caption_keeps_the_token_at_the_head_after_enforcement():
    result = clean_caption_for_mode(
        "This image shows a brass telescope",
        Path("image.png"),
        "tok",
        style_mode=False,
        annotations=[_ann("a chipped enamel mug")],
    )

    # Boilerplate stripped, label appended, token prepended — in that order.
    assert result == "tok, A brass telescope, a chipped enamel mug"


def test_style_mode_enforces_labels_without_adding_a_token():
    result = clean_caption_for_mode(
        "A brass telescope",
        Path("image.png"),
        None,
        style_mode=True,
        annotations=[_ann("a chipped enamel mug")],
    )

    assert result == "A brass telescope, a chipped enamel mug"
