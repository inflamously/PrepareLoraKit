"""Tests for the Caption Verifier text-to-image runtime.

Model loading is fully mocked at the ``loader.load_pipeline`` seam — no torch,
no diffusers, no GPU. What is under test is the runtime's own contract: seed
handling, the lock that protects a single CUDA pipeline from the bridge's
concurrent RPC thread, family-aware call kwargs, and teardown.
"""
from __future__ import annotations

import dataclasses
import io
import threading
import time
import types
from contextlib import contextmanager

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
    monkeypatch.setattr(
        t2i.runtime_env, "probe_environment", lambda: (True, 24.0, 22.0, True),
    )
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


# --- load status -----------------------------------------------------------
#
# The first click of a run pays for the model load — ten minutes for a 9B
# FLUX.2 klein at nf4. The modal has no other signal, so everything below is
# about the load being *legible* while it blocks, not about the load itself.

def _statuses(monkeypatch, **kwargs):
    published: list[dict] = []
    runtime, pipe, loads = _runtime(
        monkeypatch, status_callback=published.append, **kwargs,
    )
    monkeypatch.setattr(t2i, "_PROGRESS_INTERVAL_S", 0.02)
    return runtime, pipe, published


def test_the_loading_status_is_published_before_the_pipeline_returns(monkeypatch):
    """Published after the load, it would only ever be read as history."""
    runtime, pipe, published = _statuses(monkeypatch)
    during: dict[str, list[str]] = {}

    def fake_load(plan):
        during["phases"] = [entry["phase"] for entry in list(published)]
        return pipe

    monkeypatch.setattr(t2i.loader, "load_pipeline", fake_load)

    runtime.generate("prompt")

    assert during["phases"] == ["resolving", "loading"]
    assert published[-1]["phase"] == "ready"


def test_the_loading_status_carries_the_resolved_plan(monkeypatch):
    """``self._plan`` is not set yet mid-load, so the plan is passed explicitly."""
    runtime, _, published = _statuses(monkeypatch)

    runtime.generate("prompt")

    loading = next(entry for entry in published if entry["phase"] == "loading")
    assert loading["model_id"] == "stabilityai/stable-diffusion-xl-base-1.0"
    assert loading["device"] == "cuda"
    assert loading["family"] == "sdxl"


def test_a_slow_load_keeps_republishing_an_elapsed_count(monkeypatch):
    """A silent load and a hung one are the same picture without this."""
    runtime, pipe, published = _statuses(monkeypatch)

    def slow_load(plan):
        deadline = time.perf_counter() + 2.0
        while time.perf_counter() < deadline:
            if len([e for e in list(published) if e["phase"] == "loading"]) > 1:
                break
            time.sleep(0.01)
        return pipe

    monkeypatch.setattr(t2i.loader, "load_pipeline", slow_load)

    runtime.generate("prompt")

    ticks = [entry for entry in published if entry["phase"] == "loading"]
    assert len(ticks) > 1, "the load published once and then went silent"
    assert all("elapsed_s" in entry for entry in ticks)


def test_hugging_face_progress_bars_reach_the_status(monkeypatch):
    """diffusers' and transformers' bars are the only real progress HF exposes."""
    from tqdm.auto import tqdm

    runtime, pipe, published = _statuses(monkeypatch)

    def fake_load(plan):
        bar = tqdm(
            total=6, desc="Loading checkpoint shards",
            file=io.StringIO(), mininterval=0,
        )
        bar.update(3)
        deadline = time.perf_counter() + 2.0
        while time.perf_counter() < deadline:
            if any(entry.get("detail") for entry in list(published)):
                break
            time.sleep(0.01)
        bar.close()
        return pipe

    monkeypatch.setattr(t2i.loader, "load_pipeline", fake_load)

    runtime.generate("prompt")

    detailed = [entry for entry in published if entry.get("detail")]
    assert detailed, "no tqdm-derived detail ever reached the status"
    assert detailed[-1]["detail"] == "Loading checkpoint shards · 3/6"
    assert detailed[-1]["progress"] == pytest.approx(0.5)


def test_a_failed_load_publishes_a_failed_status(monkeypatch):
    """The error surfaces on the RPC thread; nothing else rewrites the banner."""
    runtime, _, published = _statuses(monkeypatch)

    def broken_load(plan):
        raise RuntimeError("Flux2KleinPipeline is not available")

    monkeypatch.setattr(t2i.loader, "load_pipeline", broken_load)

    with pytest.raises(RuntimeError):
        runtime.generate("prompt")

    assert published[-1]["phase"] == "failed"
    assert "Flux2KleinPipeline is not available" in published[-1]["message"]


def test_a_cached_pipeline_never_reports_loading_again(monkeypatch):
    """Only the first render of a run waits on the model; the rest go straight out."""
    runtime, _, published = _statuses(monkeypatch)
    runtime.generate("one")
    published.clear()

    runtime.generate("two")

    phases = [entry["phase"] for entry in published]
    assert phases[0] == "generating"
    assert "loading" not in phases and "resolving" not in phases


def test_a_stale_detail_never_outlives_its_phase(monkeypatch):
    """Each snapshot is rebuilt, so "3/6 shards" cannot linger over a render."""
    runtime, pipe, published = _statuses(monkeypatch)

    def fake_load(plan):
        bar = tqdm_bar()
        bar.update(3)
        deadline = time.perf_counter() + 2.0
        while time.perf_counter() < deadline:
            if any(entry.get("detail") for entry in list(published)):
                break
            time.sleep(0.01)
        bar.close()
        return pipe

    monkeypatch.setattr(t2i.loader, "load_pipeline", fake_load)

    runtime.generate("prompt")

    assert "detail" not in published[-1]


def tqdm_bar():
    from tqdm.auto import tqdm

    return tqdm(
        total=6, desc="Loading checkpoint shards", file=io.StringIO(), mininterval=0,
    )


def test_denoising_steps_report_progress(monkeypatch):
    runtime, _, published = _statuses(monkeypatch)
    seen: list[dict] = []

    class SteppingPipe(FakePipe):
        def __call__(self, **kwargs):
            callback = kwargs.get("callback_on_step_end")
            for index in range(kwargs["num_inference_steps"]):
                callback(self, index, 0, {})
            return super().__call__(**kwargs)

    pipe = SteppingPipe()
    monkeypatch.setattr(t2i.loader, "load_pipeline", lambda plan: pipe)

    runtime.generate("prompt", steps=4, cancel_check=lambda: None)

    seen = [entry for entry in published if entry["phase"] == "generating"]
    assert seen[-1]["message"] == "Denoising 4/4"
    assert seen[-1]["progress"] == pytest.approx(1.0)


# --- weights ---------------------------------------------------------------
#
# A 9B load spends minutes inside one opaque call. How much of the checkpoint
# has actually landed is the one thing the elapsed counter cannot say.

def test_the_loading_status_reports_weights_loaded(monkeypatch):
    runtime, _, published = _statuses(monkeypatch)
    _measure(monkeypatch, (6_200_000_000, 9_400_000_000))

    runtime.generate("prompt")

    assert _last_loading(published)["weights_loaded_bytes"] == 6_200_000_000
    assert _last_loading(published)["weights_total_bytes"] == 9_400_000_000


def test_the_progress_bar_follows_the_weights_not_the_current_bar(monkeypatch):
    """A tqdm fraction restarts per component; the checkpoint fraction cannot."""
    runtime, _, published = _statuses(monkeypatch)
    _measure(
        monkeypatch, (6_000_000_000, 8_000_000_000),
        # The bar for the component in flight has only just started.
        progress=t2i.load_status.LoadProgress(detail="shards", fraction=0.1),
    )

    runtime.generate("prompt")

    loading = _last_loading(published)
    assert loading["progress"] == pytest.approx(0.75)
    assert loading["detail"] == "shards"


def test_status_omits_weights_when_the_checkpoint_cannot_be_measured(monkeypatch):
    """A first-run download has nothing loaded; "0 / 0 GB" would claim it does."""
    runtime, _, published = _statuses(monkeypatch)
    _measure(monkeypatch, None)

    runtime.generate("prompt")

    assert all("weights_loaded_bytes" not in entry for entry in published)
    assert all("weights_total_bytes" not in entry for entry in published)


def _last_loading(published):
    """The newest ``loading`` snapshot.

    Not the first: that one is published before the watcher even starts, so it
    is the only tick of a load that can carry no measurement.
    """
    return [entry for entry in published if entry["phase"] == "loading"][-1]


def _measure(monkeypatch, sampled, *, progress=None):
    """Make the load's weight tracker report ``sampled`` on every tick.

    Patches ``watch`` rather than the tracker: the wiring under test is that
    ``_load_pipeline`` hands one to the watcher at all, and that whatever comes
    back on a tick reaches the published status.
    """

    @contextmanager
    def fake_watch(callback, *, interval=1.0, weights=None):
        assert weights is not None, "the load must give the watcher a tracker"
        tick = progress or t2i.load_status.LoadProgress()
        if sampled is not None:
            tick = dataclasses.replace(tick, weights=sampled)
        callback(tick)
        yield

    monkeypatch.setattr(t2i.load_status, "watch", fake_watch)
