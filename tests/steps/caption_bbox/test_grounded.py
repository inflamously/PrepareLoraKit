"""Tests for the grounded 3-pass caption pipeline (observe → compose → verify)."""
from prepare_lora_kit.steps.caption_bbox import grounded


class _FakeRuntime:
    """Records the prompts it is asked to run and returns canned per-stage text."""

    def __init__(self, responses, *, caption_prompt=None):
        self.caption_prompt = caption_prompt
        self._responses = list(responses)
        self.prompts: list[tuple[str, int]] = []

    def run_prompt(self, image, prompt_text, *, max_new_tokens):
        self.prompts.append((prompt_text, max_new_tokens))
        return self._responses.pop(0)


_IMAGE = object()  # opaque; the fake runtime never inspects it.


def test_runs_observe_compose_verify_in_order_and_returns_verified():
    runtime = _FakeRuntime(["FACTS", "DRAFT", "FINAL CAPTION"])

    result = grounded.generate_grounded_caption(
        runtime, _IMAGE, [], "tok", style_mode=False,
    )

    assert result == "FINAL CAPTION"
    observe, compose, verify = (p for p, _ in runtime.prompts)
    assert "SUBJECT:" in observe                # stage A headings
    assert "FACTS" in compose                   # observed facts fed into stage B
    assert "DRAFT" in verify                    # draft fed into stage C
    assert "tok" in compose and "tok" in verify


def test_annotation_lines_reach_observe_and_compose_prompts():
    runtime = _FakeRuntime(["FACTS", "DRAFT", "FINAL"])
    annotations = [{"label": "a red hat", "region_desc": "in the upper-left", "crop_name": ""}]

    grounded.generate_grounded_caption(
        runtime, _IMAGE, annotations, "tok", style_mode=False,
    )

    observe, compose, _verify = (p for p, _ in runtime.prompts)
    for prompt in (observe, compose):
        assert "a red hat" in prompt
        assert "in the upper-left" in prompt


def test_observe_pass_gets_a_larger_token_budget():
    runtime = _FakeRuntime(["FACTS", "DRAFT", "FINAL"])

    grounded.generate_grounded_caption(
        runtime, _IMAGE, [], "tok", style_mode=False, max_new_tokens=200,
    )

    observe_tokens = runtime.prompts[0][1]
    compose_tokens = runtime.prompts[1][1]
    assert observe_tokens >= grounded._OBSERVE_MIN_TOKENS
    assert observe_tokens > compose_tokens


def test_custom_caption_prompt_overrides_only_the_compose_stage():
    runtime = _FakeRuntime(["FACTS", "DRAFT", "FINAL"], caption_prompt="MYTEMPLATE {concept_token}")

    grounded.generate_grounded_caption(
        runtime, _IMAGE, [], "tok", style_mode=False,
    )

    observe, compose, verify = (p for p, _ in runtime.prompts)
    assert "MYTEMPLATE" in compose
    assert "MYTEMPLATE" not in observe
    assert "MYTEMPLATE" not in verify


def test_empty_verify_falls_back_to_the_draft():
    runtime = _FakeRuntime(["FACTS", "DRAFT CAPTION", "   "])

    result = grounded.generate_grounded_caption(
        runtime, _IMAGE, [], "tok", style_mode=False,
    )

    assert result == "DRAFT CAPTION"


def test_empty_compose_falls_back_to_a_single_pass_then_verifies():
    # observe → "" compose → single-pass fallback → verify == 4 runs.
    runtime = _FakeRuntime(["FACTS", "", "SINGLE PASS", "VERIFIED"])

    result = grounded.generate_grounded_caption(
        runtime, _IMAGE, [], "tok", style_mode=False,
    )

    assert result == "VERIFIED"
    assert len(runtime.prompts) == 4
    fallback_prompt = runtime.prompts[2][0]
    assert fallback_prompt.rstrip().endswith("Caption:")   # build_full_image_prompt


def test_style_mode_omits_the_concept_token_instruction():
    runtime = _FakeRuntime(["FACTS", "DRAFT", "FINAL"])

    grounded.generate_grounded_caption(
        runtime, _IMAGE, [], None, style_mode=True,
    )

    _observe, compose, verify = (p for p, _ in runtime.prompts)
    assert "trigger word" in compose
    assert "concept token" not in verify.lower()


def test_emits_each_stage_in_order():
    runtime = _FakeRuntime(["FACTS", "DRAFT", "FINAL"])
    stages = []

    grounded.generate_grounded_caption(
        runtime, _IMAGE, [], "tok", style_mode=False,
        emit=lambda stage, _message: stages.append(stage),
    )

    assert stages == ["observing", "composing", "verifying"]
