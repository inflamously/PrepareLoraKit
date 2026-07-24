"""Tests for the grounded caption pipeline (observe → compose → gap-fill)."""
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

# A draft that passes every gap-pass gate: long enough, no filler vocabulary.
_RICH_DRAFT = (
    "A weathered brass telescope stands on a wooden tripod beside a tall window, "
    "morning light falling across the polished floor and pale curtains behind it."
)


def test_runs_observe_compose_then_gap_fills_a_thin_draft():
    runtime = _FakeRuntime(["FACTS", "A brass telescope", "a red velvet curtain"])

    result = grounded.generate_grounded_caption(
        runtime, _IMAGE, [], "tok", style_mode=False,
    )

    observe, compose, gap = (p for p, _ in runtime.prompts)
    assert "SUBJECT:" in observe                 # stage A headings
    assert "FACTS" in compose                    # observed facts fed into stage B
    assert "A brass telescope" in gap            # draft fed into stage C
    assert "tok" in compose
    assert result == "A brass telescope, a red velvet curtain"


def test_a_good_draft_skips_the_gap_pass_entirely():
    runtime = _FakeRuntime(["FACTS", _RICH_DRAFT])

    result = grounded.generate_grounded_caption(
        runtime, _IMAGE, [], "tok", style_mode=False,
    )

    assert result == _RICH_DRAFT
    assert len(runtime.prompts) == 2             # no third image encode


def test_a_draft_omitting_a_region_label_gets_the_gap_pass():
    runtime = _FakeRuntime(["FACTS", _RICH_DRAFT, "a chipped enamel mug"])
    annotations = [{"label": "a chipped enamel mug", "region_desc": "on the right", "crop_name": ""}]

    result = grounded.generate_grounded_caption(
        runtime, _IMAGE, annotations, "tok", style_mode=False,
    )

    assert len(runtime.prompts) == 3
    assert result == _RICH_DRAFT.rstrip(".") + ", a chipped enamel mug."


def test_gap_pass_can_only_add_to_the_draft():
    # A model that ignores the format and tries to rewrite must not be able to.
    runtime = _FakeRuntime(["FACTS", "A brass telescope on a tripod", "A completely different caption"])

    result = grounded.generate_grounded_caption(
        runtime, _IMAGE, [], "tok", style_mode=False,
    )

    assert result.startswith("A brass telescope on a tripod")


def test_gap_pass_answering_none_leaves_the_draft_untouched():
    runtime = _FakeRuntime(["FACTS", "A brass telescope", "NONE"])

    result = grounded.generate_grounded_caption(
        runtime, _IMAGE, [], "tok", style_mode=False,
    )

    assert result == "A brass telescope"


def test_gap_pass_gets_a_small_token_budget():
    runtime = _FakeRuntime(["FACTS", "A brass telescope", "NONE"])

    grounded.generate_grounded_caption(
        runtime, _IMAGE, [], "tok", style_mode=False, max_new_tokens=200,
    )

    assert runtime.prompts[2][1] == grounded._GAP_MAX_TOKENS
    assert runtime.prompts[2][1] < runtime.prompts[1][1]


def test_annotation_lines_reach_observe_and_compose_prompts():
    runtime = _FakeRuntime(["FACTS", "DRAFT", "NONE"])
    annotations = [{"label": "a red hat", "region_desc": "in the upper-left", "crop_name": ""}]

    grounded.generate_grounded_caption(
        runtime, _IMAGE, annotations, "tok", style_mode=False,
    )

    observe, compose = (p for p, _ in runtime.prompts[:2])
    for prompt in (observe, compose):
        assert "a red hat" in prompt
        assert "in the upper-left" in prompt


def test_observe_pass_gets_a_larger_token_budget():
    runtime = _FakeRuntime(["FACTS", "DRAFT", "NONE"])

    grounded.generate_grounded_caption(
        runtime, _IMAGE, [], "tok", style_mode=False, max_new_tokens=200,
    )

    observe_tokens = runtime.prompts[0][1]
    compose_tokens = runtime.prompts[1][1]
    assert observe_tokens >= grounded._OBSERVE_MIN_TOKENS
    assert observe_tokens > compose_tokens


def test_custom_caption_prompt_overrides_only_the_compose_stage():
    runtime = _FakeRuntime(["FACTS", "DRAFT", "NONE"], caption_prompt="MYTEMPLATE {concept_token}")

    grounded.generate_grounded_caption(
        runtime, _IMAGE, [], "tok", style_mode=False,
    )

    observe, compose, gap = (p for p, _ in runtime.prompts)
    assert "MYTEMPLATE" in compose
    assert "MYTEMPLATE" not in observe
    assert "MYTEMPLATE" not in gap


def test_empty_compose_falls_back_to_a_single_pass_then_gap_fills():
    # observe → "" compose → single-pass fallback → gap == 4 runs.
    runtime = _FakeRuntime(["FACTS", "", "SINGLE PASS", "NONE"])

    result = grounded.generate_grounded_caption(
        runtime, _IMAGE, [], "tok", style_mode=False,
    )

    assert result == "SINGLE PASS"
    assert len(runtime.prompts) == 4
    fallback_prompt = runtime.prompts[2][0]
    assert fallback_prompt.rstrip().endswith("Caption:")   # build_full_image_prompt


def test_style_mode_omits_the_concept_token_instruction():
    runtime = _FakeRuntime(["FACTS", "DRAFT", "NONE"])

    grounded.generate_grounded_caption(
        runtime, _IMAGE, [], None, style_mode=True,
    )

    _observe, compose, gap = (p for p, _ in runtime.prompts)
    assert "trigger word" in compose
    assert "concept token" not in gap.lower()


def test_emits_each_stage_in_order():
    runtime = _FakeRuntime(["FACTS", "DRAFT", "NONE"])
    stages = []

    grounded.generate_grounded_caption(
        runtime, _IMAGE, [], "tok", style_mode=False,
        emit=lambda stage, _message: stages.append(stage),
    )

    assert stages == ["observing", "composing", "verifying"]


def test_no_verifying_status_is_emitted_when_the_gap_pass_is_skipped():
    runtime = _FakeRuntime(["FACTS", _RICH_DRAFT])
    stages = []

    grounded.generate_grounded_caption(
        runtime, _IMAGE, [], "tok", style_mode=False,
        emit=lambda stage, _message: stages.append(stage),
    )

    assert stages == ["observing", "composing"]
