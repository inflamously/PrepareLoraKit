from __future__ import annotations
import copy
import math
from pathlib import Path

from ...utils import image as img_utils


def _count_images(dataset_dir: Path) -> int:
    return len(img_utils.iter_images(dataset_dir))


def _epoch_math(
    n_images: int,
    repeats: int,
    batch: int,
    grad_accum: int,
) -> dict:
    steps_per_epoch = math.ceil(n_images * repeats / (batch * grad_accum))
    return {
        "n_images": n_images,
        "repeats": repeats,
        "batch": batch,
        "grad_accum": grad_accum,
        "steps_per_epoch": steps_per_epoch,
    }


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out
