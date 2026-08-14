"""Tests for caption text cleanup: reasoning removal and boilerplate stripping."""
from prepare_lora_kit.steps.caption_bbox import caption_text


def test_strip_reasoning_removes_a_closed_think_block():
    raw = "<think>The user wants a caption. I see a cat.</think>A tabby cat on a windowsill."

    assert caption_text.strip_reasoning(raw) == "A tabby cat on a windowsill."


def test_strip_reasoning_handles_a_template_prefilled_opener():
    # Qwen-style chat templates append "<think>" to the prompt itself, so generation
    # starts *inside* the block and only the closing tag is ever decoded.
    raw = "Let me look. The main subject is a cat.</think>A tabby cat on a windowsill."

    assert caption_text.strip_reasoning(raw) == "A tabby cat on a windowsill."


def test_strip_reasoning_drops_a_thought_truncated_by_the_token_budget():
    # max_new_tokens ran out mid-thought, so there is no caption in here at all.
    # Returning the fragment would write reasoning into the training .txt file.
    raw = "<think>The user wants a caption. First I should identify the main sub"

    assert caption_text.strip_reasoning(raw) == ""


def test_strip_reasoning_removes_every_block():
    raw = "<think>one</think>A cat<think>two</think> on a sill."

    assert caption_text.strip_reasoning(raw) == "A cat on a sill."


def test_strip_reasoning_is_case_insensitive_and_covers_tag_variants():
    assert caption_text.strip_reasoning("<Think>hmm</Think>A cat.") == "A cat."
    assert caption_text.strip_reasoning("<thinking>hmm</thinking>A cat.") == "A cat."


def test_strip_reasoning_leaves_an_ordinary_caption_untouched():
    raw = "A tabby cat on a windowsill, morning light across the floor."

    assert caption_text.strip_reasoning(raw) == raw


def test_strip_reasoning_keeps_prose_that_merely_mentions_thinking():
    # Guards the tag regex against matching plain words: a caption may legitimately
    # describe someone thinking, and that text must survive.
    raw = "A man in a thinking pose, chin resting on one hand."

    assert caption_text.strip_reasoning(raw) == raw


def test_strip_reasoning_tolerates_blank_input():
    assert caption_text.strip_reasoning("") == ""
    assert caption_text.strip_reasoning(None) == ""


def test_strip_boilerplate_still_runs_on_the_text_behind_a_thought():
    # The two cleanups compose: reasoning first, then the lead-in phrase it hid.
    raw = "<think>hmm</think>This image shows a brass telescope."

    assert caption_text.strip_boilerplate(caption_text.strip_reasoning(raw)) == (
        "A brass telescope."
    )
