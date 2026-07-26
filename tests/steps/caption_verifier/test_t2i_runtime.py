"""Tests for the Caption Verifier text-to-image runtime.

Model loading is fully mocked at the ``loader.load_pipeline`` seam — no torch,
no diffusers, no GPU. What is under test is the runtime's own contract: seed
handling, the lock that protects a single CUDA pipeline from the bridge's
concurrent RPC thread, family-aware call kwargs, and teardown.
"""
from __future__ import annotations

import threading
import time
import types

import pytest
from PIL import Image

from prepare_lora_kit.steps.caption_verifier import catalog, t2i


class FakePipe:
    """Records call kwargs and returns a deterministic 8x8 image."""

    def __init__(self, *, delay: float = 0.0, tokenizer=None):
        self.calls: list[dict] = []
        self.freed = 0
        self.delay = delay
        self.tokenizer = tokenizer
        self.active = 0
        self.max_concurrent = 0

    def __call__(self, **kwargs):
        self.active += 1
        self.max_concurrent = max(self.max_concurrent, self.active)
        try:
            self.calls.append(kwargs)
            if self.delay:
                time.sleep(self.delay)
            return types.SimpleNamespace(images=[Image.new("RGB", (8, 8), "blue")])
        finally:
            self.active -= 1

    def maybe_free_model_hooks(self):
        self.freed += 1


class FakeTokenizer:
    def __init__(self, token_count: int, model_max_length: int = 77):
        self.token_count = token_count
        self.model_max_length = model_max_length

    def __call__(self, text, **kwargs):
        return {"input_ids": [list(range(self.token_count))]}


@pytest.fixture(autouse=True)
def _clear_cache():
    t2i.unload()
    yield
    t2i.unload()


def _runtime(monkeypatch, pipe=None, model_id=None, **kwargs):
    pipe = pipe or FakePipe()
    loads = {"count": 0}

    def fake_load(plan):
        loads["count"] += 1
        return pipe

    monkeypatch.setattr(t2i.loader, "load_pipeline", fake_load)
    monkeypatch.setattr(t2i, "_probe_environment", lambda: (True, 24.0, 22.0, True))
    runtime = t2i.T2IRuntime(
        model_id=model_id or "stabilityai/stable-diffusion-xl-base-1.0", **kwargs,
    )
    return runtime, pipe, loads


# --- seeds -----------------------------------------------------------------

def test_generate_uses_and_reports_the_requested_seed(monkeypatch):
    runtime, pipe, _ = _runtime(monkeypatch)

    result = runtime.generate("a red cube", seed=1234)

    assert result.seed == 1234
    assert len(pipe.calls) == 1


def test_generate_without_a_seed_rolls_a_fresh_one(monkeypatch):
    runtime, _, _ = _runtime(monkeypatch)
    values = iter([b"\x00\x00\x00\x01", b"\x00\x00\x00\x02"])
    monkeypatch.setattr(t2i.os, "urandom", lambda n: next(values))

    first = runtime.generate("prompt")
    second = runtime.generate("prompt")

    assert first.seed != second.seed
    assert {first.seed, second.seed} == {1, 2}


# --- caching and teardown --------------------------------------------------

def test_pipeline_is_loaded_once_across_generations(monkeypatch):
    runtime, _, loads = _runtime(monkeypatch)

    runtime.generate("one")
    runtime.generate("two")

    assert loads["count"] == 1


def test_pipeline_is_not_loaded_until_the_first_generate(monkeypatch):
    """The user may open the modal and never click Generate."""
    _runtime_obj, _pipe, loads = _runtime(monkeypatch)

    assert loads["count"] == 0


def test_unload_frees_model_hooks_and_clears_the_cache(monkeypatch):
    runtime, pipe, _ = _runtime(monkeypatch)
    runtime.generate("prompt")

    runtime.unload()

    # accelerate's offload hooks keep GPU buffers alive until freed.
    assert pipe.freed == 1
    assert t2i._CACHE == {}


def test_unload_is_safe_before_any_load(monkeypatch):
    runtime, pipe, _ = _runtime(monkeypatch)

    runtime.unload()

    assert pipe.freed == 0


# --- concurrency -----------------------------------------------------------

def test_generate_is_serialized_by_the_lock(monkeypatch):
    """The bridge RPC thread and a second click must never enter CUDA together."""
    pipe = FakePipe(delay=0.05)
    runtime, _, _ = _runtime(monkeypatch, pipe=pipe)
    errors: list[BaseException] = []

    def worker():
        try:
            runtime.generate("prompt")
        except BaseException as exc:  # pragma: no cover - surfaced by assert
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(pipe.calls) == 4
    assert pipe.max_concurrent == 1


# --- family-aware call kwargs ---------------------------------------------

def test_negative_prompt_is_passed_for_sdxl(monkeypatch):
    runtime, pipe, _ = _runtime(monkeypatch, negative_prompt="blurry")

    runtime.generate("prompt")

    assert pipe.calls[0]["negative_prompt"] == "blurry"


def test_negative_prompt_is_omitted_for_flux2(monkeypatch):
    """Verified against diffusers 0.38: Flux2KleinPipeline takes no negative_prompt."""
    runtime, pipe, _ = _runtime(
        monkeypatch,
        model_id="black-forest-labs/FLUX.2-klein-base-9B",
        negative_prompt="blurry",
    )

    runtime.generate("prompt")

    assert "negative_prompt" not in pipe.calls[0]


def test_family_defaults_drive_steps_and_guidance(monkeypatch):
    runtime, pipe, _ = _runtime(
        monkeypatch, model_id="stable-diffusion-v1-5/stable-diffusion-v1-5",
    )
    sd15 = catalog.get("stable-diffusion-v1-5/stable-diffusion-v1-5")

    runtime.generate("prompt")

    assert pipe.calls[0]["num_inference_steps"] == sd15.default_steps
    assert pipe.calls[0]["guidance_scale"] == pytest.approx(sd15.default_guidance)
    assert pipe.calls[0]["width"] == sd15.default_width


def test_per_call_overrides_win_over_the_plan(monkeypatch):
    runtime, pipe, _ = _runtime(monkeypatch)

    runtime.generate("prompt", steps=4, guidance=1.5, width=512, height=512)

    call = pipe.calls[0]
    assert call["num_inference_steps"] == 4
    assert call["guidance_scale"] == pytest.approx(1.5)
    assert (call["width"], call["height"]) == (512, 512)


# --- prompt truncation ----------------------------------------------------

def test_generate_flags_clip_truncation(monkeypatch):
    """A term past position 77 was never seen by a CLIP encoder.

    Without this flag a user would blame the model for a verdict the tokenizer
    already decided.
    """
    pipe = FakePipe(tokenizer=FakeTokenizer(token_count=90, model_max_length=77))
    runtime, _, _ = _runtime(monkeypatch, pipe=pipe)

    result = runtime.generate("a very long caption")

    assert result.truncated is True
    assert result.token_count == 90


def test_generate_does_not_flag_short_prompts(monkeypatch):
    pipe = FakePipe(tokenizer=FakeTokenizer(token_count=20, model_max_length=77))
    runtime, _, _ = _runtime(monkeypatch, pipe=pipe)

    result = runtime.generate("short")

    assert result.truncated is False
    assert result.token_count == 20


def test_missing_tokenizer_leaves_truncation_unknown(monkeypatch):
    runtime, _, _ = _runtime(monkeypatch)

    result = runtime.generate("prompt")

    assert result.truncated is False
    assert result.token_count is None


# --- metadata --------------------------------------------------------------

def test_metadata_is_available_before_loading(monkeypatch):
    runtime, _, _ = _runtime(monkeypatch)

    meta = runtime.metadata

    assert meta["model_id"] == "stabilityai/stable-diffusion-xl-base-1.0"
    assert meta["loaded"] is False


def test_metadata_reports_the_resolved_plan_after_loading(monkeypatch):
    runtime, _, _ = _runtime(monkeypatch)
    runtime.generate("prompt")

    meta = runtime.metadata

    assert meta["loaded"] is True
    assert meta["family"] == "sdxl"
    assert meta["device"] == "cuda"


def test_blank_prompt_is_rejected(monkeypatch):
    runtime, _, _ = _runtime(monkeypatch)

    with pytest.raises(ValueError, match="prompt"):
        runtime.generate("   ")
