"""Total-VRAM detection for Auto embedding-model selection.

Mirrors the detection used by the caption step (``s5_caption/vlm.py``); kept
separate so the catalog can stay torch-free.
"""
from __future__ import annotations


def total_vram_gb() -> float:
    """Total VRAM of CUDA device 0 in GiB, or ``0.0`` when CUDA is unavailable."""
    try:
        import torch

        if not torch.cuda.is_available():
            return 0.0
        props = torch.cuda.get_device_properties(0)
        return float(props.total_memory) / (1024 ** 3)
    except Exception:
        return 0.0
