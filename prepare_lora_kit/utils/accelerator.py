"""Best-effort release of ML accelerator resources between pipeline steps."""
from __future__ import annotations

import gc
import sys
from typing import Any


def release_accelerator_memory() -> None:
    """Collect unreachable model graphs and return cached CUDA memory.

    PyTorch is discovered through ``sys.modules`` so a non-ML pipeline does not
    import it or initialize an accelerator runtime. Cleanup is best-effort and
    must never hide the step's actual success, failure, or cancellation.
    """
    torch: Any = sys.modules.get("torch")
    if torch is None:
        return

    cuda = getattr(torch, "cuda", None)
    initialized = False
    if cuda is not None:
        try:
            initialized = bool(cuda.is_initialized())
        except Exception:
            initialized = False

    if initialized:
        try:
            cuda.synchronize()
        except Exception:
            pass

    gc.collect()

    if initialized:
        try:
            cuda.empty_cache()
        except Exception:
            pass
