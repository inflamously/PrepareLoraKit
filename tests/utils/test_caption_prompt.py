"""Direct tests for the caption prompt builders in ``utils.caption``.

Pure string layer — no torch/transformers, no model loading.
"""
from prepare_lora_kit.utils import caption as cap_utils


def test_concept_prompt_has_token_and_grounding():
    prompt = cap_utils.build_full_image_prompt([], "sks")

    # Concept token is threaded in and requested explicitly.
    assert "sks" in prompt
    assert "Includes the concept token exactly as written" in prompt
    # Anti-hallucination grounding clause is present.
    assert "clearly and directly visible" in prompt
    assert "Do not invent" in prompt
    # Empty-annotation placeholder is filled (not left as a raw brace).
    assert "{bbox_annotations}" not in prompt
    assert "(no annotations — describe the full image)" in prompt


def test_style_prompt_has_grounding_and_no_token_instruction():
    prompt = cap_utils.build_full_image_prompt([], None)

    assert "clearly and directly visible" in prompt
    assert "Do not invent" in prompt
    # Style mode must not ask for a trigger/concept token.
    assert "concept token exactly as written" not in prompt
    assert "{concept_token}" not in prompt


def test_softened_structure_allows_omitting_absent_elements():
    prompt = cap_utils.build_full_image_prompt([], "sks")
    # The rigid "Follows this structure" mandate is gone; omission is explicit.
    assert "Follows this structure" not in prompt
    assert "Omit any element that is not present" in prompt


def test_apply_placeholders_replaces_token_and_leaves_unknown_braces():
    out = cap_utils.apply_prompt_placeholders("x {concept_token} {y}", "ann", "sks")
    assert out == "x sks {y}"


def test_apply_placeholders_none_token_becomes_empty():
    out = cap_utils.apply_prompt_placeholders("[{concept_token}]", "ann", None)
    assert out == "[]"


def test_custom_template_bypasses_builtin():
    prompt = cap_utils.build_full_image_prompt(
        [], "sks", template="literal {concept_token} caption"
    )
    assert prompt == "literal sks caption"


def test_default_prompt_text_matches_constants():
    assert cap_utils.default_prompt_text("full_image") == cap_utils._FULL_IMAGE_PROMPT_CONCEPT
    assert cap_utils.default_prompt_text("region") == cap_utils._REGION_PROMPT
