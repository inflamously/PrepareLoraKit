"""Tests for prompt assembly: domain brief, abstention, and grounding sections."""
from prepare_lora_kit.steps.caption_bbox import prompts


_BRIEF = "Screenshots from the game Foo. Call the blue cylinders 'flux capsules'."


def _ann(label="a red hat"):
    return {"label": label, "region_desc": "in the upper-left", "crop_name": ""}


# ── Domain brief ───────────────────────────────────────────────────────────────

def test_domain_brief_is_prepended_and_marked_authoritative():
    result = prompts.apply_domain_brief("INSTRUCTION", _BRIEF)

    assert result.startswith("Domain context")
    assert _BRIEF in result
    assert result.rstrip().endswith("INSTRUCTION")
    assert "outranks your own assumptions" in result


def test_blank_domain_brief_changes_nothing():
    assert prompts.apply_domain_brief("INSTRUCTION", None) == "INSTRUCTION"
    assert prompts.apply_domain_brief("INSTRUCTION", "   ") == "INSTRUCTION"


def test_every_naming_prompt_carries_the_domain_brief():
    built = [
        prompts.build_observe_prompt([], domain_brief=_BRIEF),
        prompts.build_compose_prompt("FACTS", [], "tok", style_mode=False, domain_brief=_BRIEF),
        prompts.build_full_image_prompt([], "tok", domain_brief=_BRIEF),
        prompts.build_region_prompt("in the center", domain_brief=_BRIEF),
    ]

    for prompt in built:
        assert _BRIEF in prompt


def test_domain_brief_also_reaches_user_authored_templates():
    # The library prompt cannot opt in, so the brief must be applied around it.
    compose = prompts.build_compose_prompt(
        "", [], "tok", style_mode=False, template="MYTEMPLATE", domain_brief=_BRIEF,
    )
    region = prompts.build_region_prompt(None, template="MYREGION", domain_brief=_BRIEF)

    assert _BRIEF in compose and "MYTEMPLATE" in compose
    assert _BRIEF in region and "MYREGION" in region


# ── Abstention ─────────────────────────────────────────────────────────────────

def test_observe_prompt_offers_an_abstention_route():
    prompt = prompts.build_observe_prompt([])

    assert "cannot confidently name it" in prompt
    assert '"?"' in prompt


def test_compose_explains_the_marker_only_when_facts_use_it():
    with_marker = prompts.build_compose_prompt(
        "SUBJECT: ? a segmented metal object", [], "tok", style_mode=False,
    )
    without = prompts.build_compose_prompt("SUBJECT: a telescope", [], "tok", style_mode=False)

    assert "could not confidently name" in with_marker
    assert "could not confidently name" not in without


def test_single_pass_and_region_prompts_prefer_description_over_a_guess():
    for prompt in (
        prompts.build_full_image_prompt([], "tok"),
        prompts.build_region_prompt(None),
        prompts.build_region_prompt("in the center"),
    ):
        assert "confidently name" in prompt


# ── Grounding sections ─────────────────────────────────────────────────────────

def test_labels_are_declared_ground_truth_on_both_grounding_paths():
    observed = prompts.build_compose_prompt("FACTS", [_ann()], "tok", style_mode=False)
    annotated = prompts.build_compose_prompt("", [_ann()], "tok", style_mode=False)

    for prompt in (observed, annotated):
        assert "ground truth" in prompt
        assert "never rename or contradict them" in prompt
        assert "a red hat" in prompt


def test_unannotated_compose_says_so_plainly():
    prompt = prompts.build_compose_prompt("FACTS", [], "tok", style_mode=False)

    assert "No regions were annotated" in prompt
    assert "ground truth" not in prompt


def test_annotation_led_compose_asks_for_global_attributes_from_the_image():
    prompt = prompts.build_compose_prompt("", [_ann()], "tok", style_mode=False)

    assert "No separate observation pass was run" in prompt
    assert "lighting" in prompt and "directly from the image" in prompt


def test_no_leftover_placeholders_in_any_built_prompt():
    built = [
        prompts.build_observe_prompt([_ann()], domain_brief=_BRIEF),
        prompts.build_compose_prompt("FACTS", [_ann()], "tok", style_mode=False),
        prompts.build_compose_prompt("", [_ann()], None, style_mode=True),
        prompts.build_full_image_prompt([_ann()], "tok"),
        prompts.build_gap_prompt("A draft caption"),
        prompts.build_region_prompt("in the center"),
    ]

    for prompt in built:
        for placeholder in ("{facts", "{annotations_section}", "{bbox_annotations}",
                            "{concept_token}", "{domain_brief}", "{draft}", "{region_position}"):
            assert placeholder not in prompt
