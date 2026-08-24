import sys
from types import SimpleNamespace

import pytest

from prepare_lora_kit.steps.caption_bbox import vlm


def _fake_loaded(
    *,
    supports_prompt: bool,
    processor=None,
    model_id: str = "fake/model",
    model_type: str = "fake",
) -> SimpleNamespace:
    return SimpleNamespace(
        supports_prompt=supports_prompt,
        adapter="fake",
        device="cpu",
        quantization="none",
        dtype="bfloat16",
        max_pixels=vlm._DEFAULT_MAX_PIXELS,
        model=SimpleNamespace(
            name_or_path=model_id,
            config=SimpleNamespace(model_type=model_type),
        ),
        processor=processor,
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


def test_8bit_model_kwargs_allow_inferred_cpu_offload(monkeypatch):
    class _BitsAndBytesConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(BitsAndBytesConfig=_BitsAndBytesConfig),
    )

    kwargs = vlm._model_kwargs("8bit", "bfloat16")

    assert kwargs["device_map"] == "auto"
    assert kwargs["quantization_config"].kwargs == {
        "load_in_8bit": True,
        "llm_int8_enable_fp32_cpu_offload": True,
    }

    kwargs = vlm._model_kwargs("4bit", "bfloat16")
    assert kwargs["quantization_config"].kwargs["load_in_4bit"] is True
    assert kwargs["quantization_config"].kwargs["llm_int8_enable_fp32_cpu_offload"] is True


def test_qwen3_prompted_loader_does_not_try_qwen2_class(monkeypatch):
    captured = {}

    def _capture(model_id, class_names, model_kwargs):
        captured["class_names"] = class_names
        return object()

    monkeypatch.setattr(vlm, "_try_model_classes", _capture)
    monkeypatch.setattr(vlm, "_require_qwen3_transformers", lambda: None)

    vlm._load_prompted_model("Qwen/Qwen3.8-27B", {})

    assert captured["class_names"] == ("AutoModelForImageTextToText",)


def test_qwen3_rejects_transformers_with_broken_recurrent_cache(monkeypatch):
    import importlib.metadata

    real_version = importlib.metadata.version
    monkeypatch.setattr(
        importlib.metadata,
        "version",
        lambda package: "5.12.1" if package == "transformers" else real_version(package),
    )

    with pytest.raises(RuntimeError, match=r"requires transformers>=5\.15\.1"):
        vlm._require_qwen3_transformers()


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
            raise TypeError(
                "apply_chat_template() got an unexpected keyword argument 'enable_thinking'"
            )
        self.kwargs = kwargs
        return "PROMPT"


_MESSAGES = [{"role": "user", "content": [{"type": "text", "text": "describe"}]}]


class _NativeProcessor:
    def __init__(self, *, parsed=None, error=None):
        self.tokenizer = SimpleNamespace(response_template=None)
        self.parsed = parsed
        self.error = error
        self.messages = None
        self.kwargs = None
        self.parse_args = None

    def apply_chat_template(self, messages, **kwargs):
        if self.error is not None:
            raise self.error
        self.messages = messages
        self.kwargs = kwargs
        return {"input_ids": [[11, 12, 13]], "pixel_values": "PIXELS"}

    def decode(self, generated_ids, **kwargs):
        return "unparsed reasoning and answer"

    def parse_response(self, generated_ids, schema, *, prefix):
        self.parse_args = (generated_ids, schema, prefix)
        return self.parsed


class _LegacyProcessor(_RecordingProcessor):
    def __init__(self):
        super().__init__()
        self.processor_kwargs = None

    def __call__(self, **kwargs):
        self.processor_kwargs = kwargs
        return {"input_ids": [[1, 2, 3]], "pixel_values": "LEGACY_PIXELS"}


class _PrefixlessQwenProcessor(_NativeProcessor):
    """Transformers 5.12-style processor whose parser has no prefix keyword."""

    def decode(self, token_ids, **kwargs):
        if token_ids == [11, 12, 13]:
            return "<|im_start|>assistant\n<think>\n"
        return "I should inspect the image.</think>A clean caption.<|im_end|>"

    def parse_response(self, generated_ids, schema):
        pytest.fail("the prefix-less parser cannot safely identify the assistant boundary")


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


def test_native_prompted_inputs_keep_image_in_chat_and_disable_thinking():
    processor = _NativeProcessor()
    loaded = _fake_loaded(
        supports_prompt=True,
        processor=processor,
        model_id="Qwen/Qwen3.8-27B",
        model_type="qwen3_5",
    )
    image = object()
    messages = [{
        "role": "user",
        "content": [{"type": "image", "image": image}, {"type": "text", "text": "caption"}],
    }]

    inputs = vlm._prepare_prompted_inputs(loaded, messages, image)

    assert inputs["pixel_values"] == "PIXELS"
    assert processor.messages[0]["content"][0]["image"] is image
    assert processor.kwargs == {
        "tokenize": True,
        "add_generation_prompt": True,
        "enable_thinking": False,
        "return_dict": True,
        "return_tensors": "pt",
    }


def test_non_qwen_model_keeps_legacy_two_stage_processing():
    processor = _LegacyProcessor()
    loaded = _fake_loaded(supports_prompt=True, processor=processor)
    image = object()

    inputs = vlm._prepare_prompted_inputs(loaded, _MESSAGES, image)

    assert processor.kwargs["tokenize"] is False
    assert processor.processor_kwargs == {
        "text": ["PROMPT"],
        "images": [image],
        "return_tensors": "pt",
    }
    assert inputs["pixel_values"] == "LEGACY_PIXELS"


def test_qwen_response_parser_returns_content_without_thinking():
    processor = _NativeProcessor(parsed={
        "role": "assistant",
        "thinking": "First I should inspect the image.",
        "content": "A brass telescope on a wooden tripod.",
    })
    loaded = _fake_loaded(
        supports_prompt=True,
        processor=processor,
        model_id="Qwen/Qwen3.8-27B",
        model_type="qwen3_5",
    )

    result = vlm._decode_prompted_response(loaded, [21, 22], [11, 12, 13])

    assert result == "A brass telescope on a wooden tripod."
    generated, schema, prefix = processor.parse_args
    assert generated == [21, 22]
    assert schema == vlm._QWEN_RESPONSE_TEMPLATE
    assert prefix == [11, 12, 13]


def test_qwen_without_structured_parser_uses_prefill_aware_compatibility_path():
    processor = _PrefixlessQwenProcessor()
    processor.parse_response = None
    loaded = _fake_loaded(
        supports_prompt=True,
        processor=processor,
        model_id="Qwen/Qwen3.8-27B",
        model_type="qwen3_5",
    )

    result = vlm._decode_prompted_response(loaded, [21, 22], [11, 12, 13])

    assert result == "A clean caption."


def test_qwen_prefixless_transformers_parser_uses_compatibility_path():
    processor = _PrefixlessQwenProcessor()
    loaded = _fake_loaded(
        supports_prompt=True,
        processor=processor,
        model_id="Qwen/Qwen3.8-27B",
        model_type="qwen3_5",
    )

    result = vlm._decode_prompted_response(loaded, [21, 22], [11, 12, 13])

    assert result == "A clean caption."


def test_native_prompting_does_not_swallow_unrelated_type_error():
    processor = _NativeProcessor(error=TypeError("image preprocessing failed"))
    loaded = _fake_loaded(supports_prompt=True, processor=processor)

    with pytest.raises(TypeError, match="image preprocessing failed"):
        vlm._prepare_prompted_inputs(loaded, _MESSAGES, object())


def test_qwen_fails_closed_if_processor_cannot_disable_thinking():
    processor = _NativeProcessor(
        error=TypeError("got an unexpected keyword argument 'enable_thinking'")
    )
    loaded = _fake_loaded(
        supports_prompt=True,
        processor=processor,
        model_id="Qwen/Qwen3.8-27B",
        model_type="qwen3_5",
    )

    with pytest.raises(RuntimeError, match="thinking disabled"):
        vlm._prepare_prompted_inputs(loaded, _MESSAGES, object())


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
