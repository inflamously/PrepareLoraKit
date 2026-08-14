from types import SimpleNamespace

import pytest

from prepare_lora_kit.steps.caption_bbox import vlm


def _fake_loaded(*, supports_prompt: bool) -> SimpleNamespace:
    return SimpleNamespace(
        supports_prompt=supports_prompt,
        adapter="fake",
        device="cpu",
        quantization="none",
        dtype="bfloat16",
        max_pixels=vlm._DEFAULT_MAX_PIXELS,
        model=SimpleNamespace(name_or_path="fake/model"),
        processor=None,
    )


def _runtime_with_loaded(monkeypatch, *, supports_prompt: bool, strategy: str = "grounded"):
    runtime = vlm.CaptionRuntime("fake/model", caption_strategy=strategy)
    runtime._loaded = _fake_loaded(supports_prompt=supports_prompt)
    # Grounded/single never touch the filesystem in these dispatch tests.
    monkeypatch.setattr(vlm, "_load_image", lambda path, max_pixels: object())
    return runtime


def test_caption_image_dispatches_to_grounded_for_prompted_model(monkeypatch, tmp_path):
    runtime = _runtime_with_loaded(monkeypatch, supports_prompt=True, strategy="grounded")
    calls = {}

    def _fake_grounded(rt, image, ann_lines, concept_token, **kw):
        calls["ann_lines"] = ann_lines
        calls["concept_token"] = concept_token
        return "GROUNDED CAPTION"

    monkeypatch.setattr(vlm.grounded, "generate_grounded_caption", _fake_grounded)
    monkeypatch.setattr(runtime, "_run", lambda *a, **k: pytest.fail("single path used"))

    result = runtime.caption_image(tmp_path / "img.png", [], "tok", max_new_tokens=200)

    assert result == "GROUNDED CAPTION"
    assert calls["concept_token"] == "tok"


def test_caption_image_uses_single_path_for_classic_model(monkeypatch, tmp_path):
    runtime = _runtime_with_loaded(monkeypatch, supports_prompt=False, strategy="grounded")
    monkeypatch.setattr(
        vlm.grounded, "generate_grounded_caption",
        lambda *a, **k: pytest.fail("grounded used for non-prompted model"),
    )
    monkeypatch.setattr(runtime, "_run", lambda image, prompt, tokens: "a plain scene")

    result = runtime.caption_image(
        tmp_path / "img.png",
        [{"x1": 0.1, "y1": 0.1, "x2": 0.4, "y2": 0.4, "label": "a red hat"}],
        "tok",
        max_new_tokens=200,
    )

    # Classic path grafts the region label and prepends the token.
    assert "a red hat" in result
    assert result.lower().startswith("tok")


def test_caption_image_single_strategy_skips_grounded_for_prompted_model(monkeypatch, tmp_path):
    runtime = _runtime_with_loaded(monkeypatch, supports_prompt=True, strategy="single")
    monkeypatch.setattr(
        vlm.grounded, "generate_grounded_caption",
        lambda *a, **k: pytest.fail("grounded used when strategy=single"),
    )
    # _run normally strips/capitalizes inside _run_prompted; mocked here, so
    # caption_image returns exactly what the single generation pass produced.
    monkeypatch.setattr(runtime, "_run", lambda image, prompt, tokens: "a single caption")

    result = runtime.caption_image(tmp_path / "img.png", [], "tok", max_new_tokens=200)

    assert result == "a single caption"


_BOX = {"x1": 0.05, "y1": 0.05, "x2": 0.25, "y2": 0.25}  # small, upper-left


def test_caption_region_captions_the_crop_with_position_hint(monkeypatch, tmp_path):
    # The region caption must describe the box contents only — the model sees the
    # CROP, never the full image; the box position is just an origin hint.
    runtime = _runtime_with_loaded(monkeypatch, supports_prompt=True)
    monkeypatch.setattr(vlm, "_load_image", lambda path, max_pixels: str(path))
    runs = []
    monkeypatch.setattr(
        runtime, "_run",
        lambda image, prompt, tokens: runs.append((image, prompt)) or "a leather belt",
    )

    result = runtime.caption_region(
        tmp_path / "crop.png", source_path=tmp_path / "img.png", box=_BOX
    )

    assert result == "a leather belt"
    image, prompt = runs[0]
    assert image == str(tmp_path / "crop.png")        # the crop, never the source image
    assert "upper-left" in prompt                     # origin hint from the box
    assert "cropped detail" in prompt                 # crop-scoped instruction
    assert "not a full-scene sentence" in prompt


def test_caption_region_without_box_uses_plain_natural_prompt(monkeypatch, tmp_path):
    runtime = _runtime_with_loaded(monkeypatch, supports_prompt=True)
    runs = []
    monkeypatch.setattr(
        runtime, "_run",
        lambda image, prompt, tokens: runs.append((image, prompt)) or "a thing",
    )

    class _Crop:
        def convert(self, mode):
            return SimpleNamespace(size=(8, 8), resize=lambda *a, **k: self)

    runtime.caption_region(_Crop())

    _image, prompt = runs[0]
    assert "cropped detail taken from" not in prompt  # no origin hint without a box
    assert "not a list of tags" in prompt             # natural-phrase, not tag-style


def test_caption_region_non_prompted_model_gets_crop_without_hint(monkeypatch, tmp_path):
    # Classic image-to-text models ignore instructions; the position hint is
    # pointless, but the crop input is what matters.
    runtime = _runtime_with_loaded(monkeypatch, supports_prompt=False)
    monkeypatch.setattr(vlm, "_load_image", lambda path, max_pixels: str(path))
    runs = []
    monkeypatch.setattr(
        runtime, "_run",
        lambda image, prompt, tokens: runs.append((image, prompt)) or "a thing",
    )

    runtime.caption_region(tmp_path / "crop.png", source_path=tmp_path / "img.png", box=_BOX)

    image, prompt = runs[0]
    assert image == str(tmp_path / "crop.png")
    assert "cropped detail taken from" not in prompt


def test_caption_region_custom_prompt_gets_position_placeholder(monkeypatch, tmp_path):
    runtime = _runtime_with_loaded(monkeypatch, supports_prompt=True)
    runtime.region_prompt = "Describe the area {region_position} briefly."
    monkeypatch.setattr(vlm, "_load_image", lambda path, max_pixels: "FULL_IMAGE")
    runs = []
    monkeypatch.setattr(
        runtime, "_run",
        lambda image, prompt, tokens: runs.append(prompt) or "a thing",
    )

    runtime.caption_region("CROP", source_path=tmp_path / "img.png", box=_BOX)

    assert "upper-left" in runs[0]
    assert "{region_position}" not in runs[0]


def test_region_position_rejects_malformed_boxes():
    assert vlm._region_position(None) is None
    assert vlm._region_position({"x1": 0.1}) is None
    assert vlm._region_position({"x1": "a", "y1": 0, "x2": 1, "y2": 1}) is None
    assert "upper-left" in vlm._region_position(_BOX)


def test_auto_quantization_uses_8bit_for_mid_vram(monkeypatch):
    class _Props:
        total_memory = 24 * 1024 ** 3

    class _Cuda:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def get_device_properties(_index):
            return _Props()

    class _Torch:
        cuda = _Cuda()

    monkeypatch.setattr(vlm, "_bitsandbytes_available", lambda: True)

    assert vlm._resolve_quantization("auto", _Torch) == "8bit"


def test_explicit_quantization_requires_bitsandbytes(monkeypatch):
    class _Cuda:
        @staticmethod
        def is_available():
            return True

    class _Torch:
        cuda = _Cuda()

    monkeypatch.setattr(vlm, "_bitsandbytes_available", lambda: False)

    with pytest.raises(RuntimeError, match="requires bitsandbytes"):
        vlm._resolve_quantization("4bit", _Torch)


def test_metadata_reports_the_generation_passes_that_ran():
    runtime = vlm.CaptionRuntime("fake/model")

    assert runtime.metadata["passes"] == {}

    runtime.note_pass("observe")
    runtime.note_pass("compose")
    runtime.note_pass("compose")

    assert runtime.metadata["passes"] == {"observe": 1, "compose": 2}


def test_pass_tally_survives_into_loaded_metadata(monkeypatch):
    runtime = _runtime_with_loaded(monkeypatch, supports_prompt=True)
    runtime.note_pass("gap")

    assert runtime.metadata["adapter"] == "fake"      # the loaded branch
    assert runtime.metadata["passes"] == {"gap": 1}


def test_runtime_normalises_and_reports_the_domain_brief():
    assert vlm.CaptionRuntime("fake/model", domain_brief="  ").domain_brief is None
    assert vlm.CaptionRuntime("fake/model").metadata["domain_brief"] is False

    runtime = vlm.CaptionRuntime("fake/model", domain_brief="  Game screenshots.  ")
    assert runtime.domain_brief == "Game screenshots."
    assert runtime.metadata["domain_brief"] is True


class _RecordingProcessor:
    """Chat-template stub that records the kwargs it was called with."""

    def __init__(self, *, accepts_thinking=True):
        self._accepts_thinking = accepts_thinking
        self.kwargs = None

    def apply_chat_template(self, messages, **kwargs):
        if "enable_thinking" in kwargs and not self._accepts_thinking:
            raise TypeError("apply_chat_template() got an unexpected keyword argument")
        self.kwargs = kwargs
        return "PROMPT"


_MESSAGES = [{"role": "user", "content": [{"type": "text", "text": "describe"}]}]


def test_chat_text_asks_the_template_to_disable_thinking():
    processor = _RecordingProcessor()

    assert vlm._build_chat_text(processor, _MESSAGES) == "PROMPT"
    assert processor.kwargs["enable_thinking"] is False
    assert processor.kwargs["add_generation_prompt"] is True


def test_chat_text_retries_without_the_kwarg_for_older_processors():
    # Most processors forward unknown kwargs into the Jinja render and ignore them,
    # but the ones that validate their signature must not break captioning.
    processor = _RecordingProcessor(accepts_thinking=False)

    assert vlm._build_chat_text(processor, _MESSAGES) == "PROMPT"
    assert "enable_thinking" not in processor.kwargs


def test_finalize_removes_reasoning_before_the_caption():
    raw = "<think>The user wants a caption.</think>This image shows a brass telescope."

    assert vlm._finalize_caption(raw) == "A brass telescope."


def test_finalize_warns_once_when_reasoning_consumed_the_whole_budget(monkeypatch):
    # A thought truncated by max_new_tokens leaves nothing behind. Empty beats
    # leaking reasoning into the dataset, but it must not fail silently.
    warnings = []
    monkeypatch.setattr(vlm.reporter, "warn", warnings.append)
    vlm._REASONING_WARNED.clear()

    assert vlm._finalize_caption("<think>First I should identify the main sub") == ""
    assert vlm._finalize_caption("<think>Another truncated thought about the") == ""

    assert len(warnings) == 1
    assert "enable_thinking" in warnings[0] or "reasoning" in warnings[0]


def test_finalize_does_not_warn_for_an_ordinary_caption(monkeypatch):
    warnings = []
    monkeypatch.setattr(vlm.reporter, "warn", warnings.append)
    vlm._REASONING_WARNED.clear()

    assert vlm._finalize_caption("A brass telescope on a tripod.") == (
        "A brass telescope on a tripod."
    )
    assert warnings == []
