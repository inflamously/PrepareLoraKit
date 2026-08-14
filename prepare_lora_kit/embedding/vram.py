"""Total-VRAM detection for Auto embedding-model selection, kept out of the catalog so
that stays torch-free.
"""
from __future__ import annotations


def total_vram_gb(device_index: int = 0) -> float:
    """Total VRAM of a CUDA device in GiB, or ``0.0`` when it is unavailable.

    Defaults to device 0. The upscale step passes an explicit index because
    SeedVR2 can be pinned to another card via ``seedvr2_cuda_device``.
    """
    try:
        import torch

        if not torch.cuda.is_available():
            return 0.0
        props = torch.cuda.get_device_properties(device_index)
        return float(props.total_memory) / (1024 ** 3)
    except Exception:
        return 0.0
