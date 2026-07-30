"""Tests for the additive gap-fill pass (gate → parse → merge).

The contract these lock down: the third caption pass can only ever *add* to a
draft. Nothing here may drop, reorder or reword text the draft (or the user)
already produced.
"""
import pytest

from prepare_lora_kit.steps.caption_bbox import gap_fill

# A draft that is long enough, mentions its labels, and carries no filler — the
# case where the gap pass should be skipped entirely.
_RICH_DRAFT = (
    "A weathered brass telescope stands on a wooden tripod beside a tall window, "
    "morning light falling across the polished floor and pale curtains behind it."
)


def _labels(*labels):
    return [{"label": label, "region_desc": "in the center", "crop_name": ""} for label in labels]


# ── needs_gap_pass ─────────────────────────────────────────────────────────────

def test_rich_draft_needs_no_gap_pass():
    assert gap_fill.needs_gap_pass(_RICH_DRAFT, _labels("brass telescope")) is None


def test_short_draft_triggers_the_gap_pass():
    assert gap_fill.needs_gap_pass("A telescope.", []) == "short_caption"


def test_missing_region_label_triggers_the_gap_pass():
    reason = gap_fill.needs_gap_pass(_RICH_DRAFT, _labels("a chipped enamel mug"))
    assert reason == "missing_label"


def test_label_counts_as_present_despite_case_and_plural_differences():
    # The draft says "pale curtains"; the label is singular and capitalised.
    assert gap_fill.needs_gap_pass(_RICH_DRAFT, _labels("Pale Curtain")) is None


def test_low_information_filler_triggers_the_gap_pass():
    draft = (
        "A beautiful scene with some kind of object resting there, rendered with "
        "care and shown against a plain flat backdrop of muted tone and colour."
    )
    assert gap_fill.needs_gap_pass(draft, []) == "low_information"


def test_low_information_match_is_word_bounded():
    # "photorealistic" must not trip the bare "realistic" filler term.
    draft = (
        "A photorealistic brass telescope on a wooden tripod beside a tall window, "
        "with morning light spilling across the polished floor behind it."
    )
    assert gap_fill.needs_gap_pass(draft, []) is None


# ── parse_gap_phrases ──────────────────────────────────────────────────────────

def test_none_sentinel_yields_no_phrases():
    assert gap_fill.parse_gap_phrases("NONE") == []
    assert gap_fill.parse_gap_phrases("  none.  ") == []


def test_parses_list_markers_and_quotes_away():
    raw = '- a red hat\n2. "a wooden bench"\n* the open window\n'
    assert gap_fill.parse_gap_phrases(raw) == ["a red hat", "a wooden bench", "the open window"]


def test_caps_the_number_of_phrases():
    raw = "one thing\ntwo thing\nthree thing\nfour thing\nfive thing"
    assert len(gap_fill.parse_gap_phrases(raw)) == 3


def test_drops_sentence_length_lines():
    raw = (
        "a red hat\n"
        "The caption does not mention that the subject is standing in a doorway "
        "beside a lamp\n"
    )
    assert gap_fill.parse_gap_phrases(raw) == ["a red hat"]


def test_drops_meta_commentary_and_header_echo():
    raw = "Missing elements:\nthe caption is fine\na brass lamp"
    assert gap_fill.parse_gap_phrases(raw) == ["a brass lamp"]


def test_none_terminates_the_list():
    assert gap_fill.parse_gap_phrases(
        "a brass lamp\nNONE\na later hallucination") == ["a brass lamp"]


def test_empty_output_yields_no_phrases():
    assert gap_fill.parse_gap_phrases("") == []
    assert gap_fill.parse_gap_phrases("   \n  \n") == []


# ── merge_missing_phrases ──────────────────────────────────────────────────────

def test_appends_a_missing_phrase():
    merged = gap_fill.merge_missing_phrases(
        "A brass telescope on a tripod", ["a red velvet curtain"])
    assert merged == "A brass telescope on a tripod, a red velvet curtain"


def test_no_phrases_leaves_the_caption_untouched():
    assert gap_fill.merge_missing_phrases(_RICH_DRAFT, []) == _RICH_DRAFT


def test_skips_a_phrase_already_covered_verbatim():
    caption = "A brass telescope on a tripod"
    assert gap_fill.merge_missing_phrases(caption, ["a brass telescope"]) == caption


def test_skips_a_phrase_whose_content_words_are_already_present():
    caption = "A brass telescope on a wooden tripod"
    # Different wording and plurality, same content — must not be appended.
    assert gap_fill.merge_missing_phrases(caption, ["the wooden tripods"]) == caption


def test_skips_a_phrase_covered_by_an_earlier_appended_phrase():
    merged = gap_fill.merge_missing_phrases("A telescope", ["a red hat", "the red hats"])
    assert merged == "A telescope, a red hat"


def test_merge_only_ever_adds_to_the_caption():
    caption = "A weathered brass telescope, gold trim, on a tripod."
    merged = gap_fill.merge_missing_phrases(caption, ["a red curtain", "an oak floor"])
    assert merged.startswith("A weathered brass telescope, gold trim, on a tripod")
    for fragment in ("weathered", "brass telescope", "gold trim", "tripod"):
        assert fragment in merged


def test_preserves_a_trailing_period():
    merged = gap_fill.merge_missing_phrases("A brass telescope.", ["a red curtain"])
    assert merged == "A brass telescope, a red curtain."


def test_respects_the_max_length_budget():
    caption = "x" * 590
    merged = gap_fill.merge_missing_phrases(caption, ["a red velvet curtain"], max_chars=600)
    assert merged == caption


def test_appends_what_fits_and_drops_the_rest():
    caption = "A telescope"
    merged = gap_fill.merge_missing_phrases(
        caption, ["a hat", "a curtain of enormous length and weight"], max_chars=25,
    )
    assert merged == "A telescope, a hat"


def test_decapitalises_an_appended_phrase():
    merged = gap_fill.merge_missing_phrases("A telescope", ["A red curtain"])
    assert merged == "A telescope, a red curtain"


def test_keeps_the_case_of_a_proper_noun_phrase():
    merged = gap_fill.merge_missing_phrases("A skyline", ["Eiffel Tower"])
    assert merged == "A skyline, Eiffel Tower"


def test_ignores_blank_and_punctuation_only_phrases():
    caption = "A telescope"
    assert gap_fill.merge_missing_phrases(caption, ["", "   ", "..."]) == caption


@pytest.mark.parametrize("phrase", ["a red hat", "an oak floor", "pale curtains"])
def test_merged_caption_is_never_shorter_than_the_draft(phrase):
    assert len(gap_fill.merge_missing_phrases(_RICH_DRAFT, [phrase])) >= len(_RICH_DRAFT)


# ── The label gate agrees with validation.enforce_region_labels ────────────────

def test_paraphrased_label_does_not_trigger_a_gap_pass():
    # Otherwise the gate spends a whole pass chasing a label that enforcement would
    # then decline to append.
    draft = (
        "A brass telescope beside a chipped mug on a wooden shelf, morning light "
        "falling across the floor and pale curtains behind it."
    )

    assert gap_fill.needs_gap_pass(draft, _labels("a chipped enamel mug with a blue rim")) is None


def test_an_unmentioned_region_still_triggers_a_gap_pass():
    assert gap_fill.needs_gap_pass(_RICH_DRAFT, _labels("a chipped mug")) == "missing_label"
