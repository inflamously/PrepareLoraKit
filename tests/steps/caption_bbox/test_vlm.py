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
