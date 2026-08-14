"""Everything CaptionVerifierStep's runtime says to torch, all of it best effort."""
from __future__ import annotations

import contextlib
import gc
import sys


def probe_environment() -> tuple[bool, float, float, bool]:
    """``(has_cuda, total_gb, free_gb, has_bitsandbytes)``.

    Isolated so tests can stub the whole environment in one place.
    """
    from prepare_lora_kit.steps.caption_verifier.plan import bitsandbytes_available

    try:
        import torch
    except Exception:
        return False, 0.0, 0.0, False

    if not torch.cuda.is_available():
        return False, 0.0, 0.0, False

    total = free = 0.0
    with contextlib.suppress(Exception):
        total = float(torch.cuda.get_device_properties(0).total_memory) / (1024 ** 3)
    try:
        free_bytes, _ = torch.cuda.mem_get_info()
        free = float(free_bytes) / (1024 ** 3)
    except Exception:
        pass
    return True, total, free, bitsandbytes_available()


def cpu_generator(seed: int):
    """Always a CPU generator.

    A CUDA generator is unreliable once accelerate's offload hooks shuffle
    modules between devices, and CPU seeding makes a seed reproducible across
    machines — which matters when a verdict is meant to be evidence.
    """
    try:
        import torch

        return torch.Generator("cpu").manual_seed(int(seed))
    except Exception:
        return None


def free_pipe(pipe) -> None:
    """Drop accelerate's offload hooks.

    The step people forget: without it the hooks keep GPU buffers alive and the
    memory never comes back, however many caches are cleared afterwards.
    """
    try:
        free_hooks = getattr(pipe, "maybe_free_model_hooks", None)
        if free_hooks is not None:
            free_hooks()
    except Exception:  # pragma: no cover - best effort
        pass


def release_memory() -> None:
    gc.collect()
    torch = _loaded_torch()
    if torch is None:
        return
    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:  # pragma: no cover - best effort
        pass


def _loaded_torch():
    """Reach torch only if something already imported it (never import here)."""
    return sys.modules.get("torch")
