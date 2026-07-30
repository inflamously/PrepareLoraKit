"""Locked, cached text-to-image runtime for CaptionVerifierStep.

Structurally mirrors ``steps/caption_bbox/vlm.py``'s ``CaptionRuntime``: a
module-level cache plus a ``threading.Lock``, because the UI reaches this object
from a **different thread** than the one that created it. While the pipeline
thread is blocked inside ``PipelineJob.request_input`` waiting for the modal,
pywebview dispatches each bridge call on its own thread — so two quick clicks
would otherwise race into the same CUDA pipeline.

This module owns the *contract* — locking, caching, seeds, truncation, and the
status it publishes while a load blocks. Its neighbours own the rest: heavy
diffusers construction in :mod:`.loader`, everything said to torch in
:mod:`.runtime_env`, and the live load progress in :mod:`.load_status`. All
heavy imports stay function-local.
"""
from __future__ import annotations

import contextlib
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from prepare_lora_kit.report import reporter
from prepare_lora_kit.steps.caption_verifier import (
    catalog,
    load_status,
    loader,
    runtime_env,
    weights,
)
from prepare_lora_kit.steps.caption_verifier.plan import GenerationPlan, resolve_plan

_CACHE: dict[tuple, LoadedT2IPipeline] = {}
# How often the load republishes itself. Faster than the UI's 800 ms poll would
# only burn ticks the frontend never reads.
_PROGRESS_INTERVAL_S = 1.0


@dataclass
class LoadedT2IPipeline:
    pipe: Any
    plan: GenerationPlan
    device: str


@dataclass
class GeneratedImage:
    """One render plus everything needed to judge and reproduce it."""

    image: Any  # PIL.Image.Image
    seed: int
    width: int
    height: int
    steps: int
    guidance: float
    elapsed_ms: int
    model_id: str
    prompt: str
    truncated: bool
    token_count: int | None

    def as_dict(self) -> dict:
        return {
            "seed": self.seed,
            "width": self.width,
            "height": self.height,
            "steps": self.steps,
            "guidance": self.guidance,
            "elapsed_ms": self.elapsed_ms,
            "model_id": self.model_id,
            "truncated": self.truncated,
            "token_count": self.token_count,
        }


class T2IRuntime:
    """A lazily loaded, lock-guarded text-to-image pipeline."""

    def __init__(
        self,
        model_id: str = "auto",
        *,
        quantization: str = "auto",
        dtype: str = "bfloat16",
        offload: str = "auto",
        width: int | None = None,
        height: int | None = None,
        steps: int | None = None,
        guidance: float | None = None,
        negative_prompt: str | None = None,
        status_callback: Callable[[dict], None] | None = None,
    ) -> None:
        self._requested_id = model_id
        self._quantization = quantization
        self._dtype = dtype
        self._offload = offload
        self._width = width
        self._height = height
        self._steps = steps
        self._guidance = guidance
        self._negative_prompt = negative_prompt
        self._status_callback = status_callback

        self._lock = threading.Lock()
        self._loaded: LoadedT2IPipeline | None = None
        self._plan: GenerationPlan | None = None
        self._key: tuple | None = None
        self._status: dict[str, Any] = {}

    # --- introspection ----------------------------------------------------

    @property
    def metadata(self) -> dict[str, Any]:
        plan = self._plan
        if plan is None:
            return {
                "model_id": catalog.normalize_id(self._requested_id),
                "loaded": False,
                "family": None,
                "pipeline_cls": None,
                "quantization": None,
                "dtype": None,
                "offload": None,
                "device": None,
                "quantize_components": [],
            }
        return {**plan.as_dict(), "loaded": self._loaded is not None}

    @property
    def status(self) -> dict[str, Any]:
        return dict(self._status)

    # --- lifecycle --------------------------------------------------------

    def load(self) -> None:
        """Load (or reuse) the pipeline. Safe to call repeatedly."""
        with self._lock:
            self._load_locked()

    def unload(self) -> None:
        """Drop the pipeline and give the VRAM back.

        ``maybe_free_model_hooks()`` is the step people forget: without it,
        accelerate's offload hooks keep GPU buffers alive and the memory never
        returns. ``utils.accelerator.release_accelerator_memory`` (which the
        engine runs after every step) cannot help, because it never drops this
        module's cache reference.
        """
        with self._lock:
            loaded, self._loaded = self._loaded, None
            key, self._key = self._key, None
            if key is not None:
                _CACHE.pop(key, None)
            if loaded is not None:
                runtime_env.free_pipe(loaded.pipe)
            self._set_status("idle", "Text-to-image model unloaded.")
        runtime_env.release_memory()

    # --- generation -------------------------------------------------------

    def generate(
        self,
        prompt: str,
        *,
        seed: int | None = None,
        width: int | None = None,
        height: int | None = None,
        steps: int | None = None,
        guidance: float | None = None,
        negative_prompt: str | None = None,
        cancel_check: Callable[[], None] | None = None,
    ) -> GeneratedImage:
        """Render ``prompt``. The whole body holds the lock, load included."""
        text = str(prompt or "").strip()
        if not text:
            raise ValueError("A non-empty prompt is required to generate a preview.")

        with self._lock:
            loaded = self._load_locked()
            plan = loaded.plan
            resolved_seed = _resolve_seed(seed)
            call_width = _coerce_int(width, plan.width)
            call_height = _coerce_int(height, plan.height)
            call_steps = _coerce_int(steps, plan.steps)
            call_guidance = float(guidance) if guidance is not None else plan.guidance

            token_count, truncated = _prompt_tokens(loaded.pipe, text, plan)
            if truncated:
                reporter.warn(
                    f"Caption verifier: prompt is {token_count} tokens but this "
                    f"encoder reads {plan.max_prompt_tokens}; the tail was never "
                    "seen by the model."
                )

            kwargs: dict[str, Any] = {
                "prompt": text,
                "num_inference_steps": call_steps,
                "guidance_scale": call_guidance,
                "width": call_width,
                "height": call_height,
                "generator": runtime_env.cpu_generator(resolved_seed),
            }
            negative = (
                negative_prompt if negative_prompt is not None else self._negative_prompt
            )
            if plan.supports_negative_prompt and negative:
                kwargs["negative_prompt"] = negative
            started = time.perf_counter()
            if cancel_check is not None:
                callback = _step_callback(
                    cancel_check, self._set_status, call_steps, plan, started,
                )
                if callback is not None:
                    kwargs["callback_on_step_end"] = callback

            self._set_status(
                "generating", f"Rendering with {plan.model_id}…", plan=plan,
            )
            try:
                result = _invoke(loaded.pipe, kwargs)
            finally:
                runtime_env.release_memory()
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            self._set_status(
                "ready", f"Rendered in {elapsed_ms / 1000:.1f}s.", plan=plan,
            )

            return GeneratedImage(
                image=result,
                seed=resolved_seed,
                width=call_width,
                height=call_height,
                steps=call_steps,
                guidance=call_guidance,
                elapsed_ms=elapsed_ms,
                model_id=plan.model_id,
                prompt=text,
                truncated=truncated,
                token_count=token_count,
            )

    # --- internals --------------------------------------------------------

    def _load_locked(self) -> LoadedT2IPipeline:
        if self._loaded is not None:
            return self._loaded

        # Emitted before probing: importing torch and waking the CUDA driver is
        # already seconds of silence, and this is the first click of the run.
        self._set_status("resolving", "Checking GPU and resolving the model…")
        has_cuda, total_gb, free_gb, has_bnb = runtime_env.probe_environment()
        model_id, model = catalog.resolve(self._requested_id, total_gb)
        plan = resolve_plan(
            model,
            model_id=model_id,
            quantization=self._quantization,
            dtype=self._dtype,
            offload=self._offload,
            total_vram_gb=total_gb,
            free_vram_gb=free_gb,
            has_cuda=has_cuda,
            has_bitsandbytes=has_bnb,
            width=self._width,
            height=self._height,
            steps=self._steps,
            guidance=self._guidance,
        )
        for note in plan.notes:
            reporter.warn(f"Caption verifier: {note}")

        key = (
            plan.model_id, plan.quantization, plan.dtype, plan.offload, plan.device,
        )
        cached = _CACHE.get(key)
        ready = f"{plan.model_id} ready."
        if cached is None:
            reporter.info(
                f"T2I model load: {plan.model_id} (family={plan.family}, "
                f"quant={plan.quantization}, dtype={plan.dtype}, "
                f"offload={plan.offload}, cuda={has_cuda}, "
                f"total_vram_gb={total_gb:.1f}, free_vram_gb={free_gb:.1f})"
            )
            pipe, load_seconds = self._load_pipeline(plan)
            reporter.ok(
                f"T2I model loaded in {load_status.format_elapsed(load_seconds)}."
            )
            ready = (
                f"{plan.model_id} ready "
                f"(loaded in {load_status.format_elapsed(load_seconds)})."
            )
            cached = LoadedT2IPipeline(
                pipe=pipe, plan=plan, device=loader.pipeline_device(pipe),
            )
            _CACHE[key] = cached

        self._plan = cached.plan
        self._loaded = cached
        self._key = key
        self._set_status("ready", ready, plan=cached.plan)
        return cached

    def _load_pipeline(self, plan: GenerationPlan) -> tuple[Any, float]:
        """Load ``plan``'s pipeline, narrating the wait. Returns ``(pipe, seconds)``.

        A 9B FLUX.2 klein at nf4 is a ten-minute call that returns nothing until
        it is done, and the modal's only other signal is a spinner — so without
        the heartbeat and the tqdm tap in :mod:`.load_status` a slow load and a
        dead one are the same picture.
        """
        started = time.perf_counter()
        message = f"Loading {plan.model_id}…"
        loaded_weights = weights.WeightProgress(
            plan.model_id, skip=loader.skipped_components(plan),
        )

        def _tick(progress: load_status.LoadProgress) -> None:
            done, total = progress.weights or (None, None)
            self._set_status(
                "loading", message, plan=plan,
                detail=progress.detail,
                progress=_load_fraction(progress),
                elapsed_s=int(time.perf_counter() - started),
                weights_loaded_bytes=done,
                weights_total_bytes=total,
            )

        _tick(load_status.LoadProgress())
        try:
            with load_status.watch(
                _tick, interval=_PROGRESS_INTERVAL_S, weights=loaded_weights,
            ):
                pipe = loader.load_pipeline(plan)
        except Exception as exc:
            # Without this the banner sits on "Loading…" for the rest of the
            # run: the exception surfaces on the RPC thread as a rejected
            # promise, and nothing else ever writes the status again.
            self._set_status(
                "failed", f"Loading {plan.model_id} failed: {exc}", plan=plan,
                elapsed_s=int(time.perf_counter() - started),
            )
            raise
        return pipe, time.perf_counter() - started

    def _set_status(
        self,
        phase: str,
        message: str,
        *,
        plan: GenerationPlan | None = None,
        **extra: Any,
    ) -> None:
        """Publish one status snapshot.

        Rebuilt from scratch every time, so a stale ``detail`` or ``progress``
        can never outlive the phase that produced it. ``plan`` is passed
        explicitly during the load, when ``self._plan`` is not set yet but the
        resolved device and quantization are already worth showing.
        """
        plan = plan or self._plan
        status: dict[str, Any] = {
            "phase": phase,
            "message": message,
            "model_id": plan.model_id if plan else catalog.normalize_id(self._requested_id),
        }
        if plan is not None:
            status.update({
                "family": plan.family,
                "device": plan.device,
                "quantization": plan.quantization,
                "dtype": plan.dtype,
                "offload": plan.offload,
            })
        status.update({k: v for k, v in extra.items() if v is not None})

        self._status = status
        if self._status_callback is not None:
            # Status is best effort; a broken listener must not fail the render.
            with contextlib.suppress(Exception):  # pragma: no cover
                self._status_callback(dict(status))


def unload() -> None:
    """Drop every cached pipeline (module-level teardown)."""
    for cached in list(_CACHE.values()):
        runtime_env.free_pipe(cached.pipe)
    _CACHE.clear()
    runtime_env.release_memory()


# --- helpers ---------------------------------------------------------------

def _load_fraction(progress: load_status.LoadProgress) -> float | None:
    """The bar's fraction for a load: weights first, tqdm second.

    A tqdm fraction belongs to one component, so a bar driven by it walks 0→100%
    once per component and lands back at the start each time — on a pipeline with
    four of them that reads as three restarts. Weight bytes are measured against
    the whole checkpoint, so the same bar only ever moves forward.
    """
    if progress.weights:
        done, total = progress.weights
        if total > 0:
            return min(1.0, done / total)
    return progress.fraction


def _coerce_int(value: int | None, fallback: int) -> int:
    if value is None:
        return int(fallback)
    return int(value)


def _resolve_seed(seed: int | None) -> int:
    if seed is None:
        return int.from_bytes(os.urandom(4), "big")
    return int(seed) % (2 ** 32)


def _invoke(pipe, kwargs: dict):
    """Call the pipeline, retrying once without kwargs it rejects.

    Custom/unknown checkpoints vary in which arguments they accept; dropping an
    unsupported one beats failing the whole probe.
    """
    try:
        result = pipe(**kwargs)
    except TypeError as exc:
        dropped = _unsupported_kwarg(str(exc), kwargs)
        if dropped is None:
            raise
        reporter.warn(
            f"Caption verifier: this pipeline rejects '{dropped}'; retrying without it."
        )
        kwargs.pop(dropped, None)
        result = pipe(**kwargs)
    images = getattr(result, "images", None)
    if not images:
        raise RuntimeError("The pipeline returned no image.")
    return images[0]


def _unsupported_kwarg(message: str, kwargs: dict) -> str | None:
    for name in ("negative_prompt", "callback_on_step_end", "guidance_scale"):
        if name in kwargs and name in message:
            return name
    return None


def _prompt_tokens(pipe, text: str, plan: GenerationPlan) -> tuple[int | None, bool]:
    """Token count and whether the encoder truncated the prompt.

    CLIP-based encoders silently cut at 77 tokens, so a term past that position
    never reached the model at all. Surfacing this stops a user blaming the
    model for something the tokenizer decided.
    """
    tokenizer = getattr(pipe, "tokenizer", None)
    if tokenizer is None:
        return None, False
    try:
        encoded = tokenizer(text, return_tensors=None, truncation=False)
        ids = encoded["input_ids"] if isinstance(encoded, dict) else encoded.input_ids
        if ids and isinstance(ids[0], (list, tuple)):
            ids = ids[0]
        count = len(ids)
    except Exception:
        return None, False

    limit = getattr(tokenizer, "model_max_length", None) or plan.max_prompt_tokens
    try:
        limit = int(limit)
    except (TypeError, ValueError):  # pragma: no cover - exotic tokenizers
        limit = plan.max_prompt_tokens
    return count, bool(limit and count > limit)


def _step_callback(cancel_check, set_status, total_steps: int, plan, started: float):
    """Abort between denoising steps so Cancel does not wait out a full render.

    ``callback_on_step_end`` is present on the SD, SDXL and FLUX.2 klein
    pipelines; a pipeline without it simply loses the early abort — and, with
    it, the only per-step progress a render ever reports.
    """

    def _callback(pipe, step_index, timestep, callback_kwargs):
        cancel_check()
        done = step_index + 1
        set_status(
            "generating", f"Denoising {done}/{total_steps}", plan=plan,
            progress=(done / total_steps) if total_steps else None,
            elapsed_s=int(time.perf_counter() - started),
        )
        return callback_kwargs

    return _callback
