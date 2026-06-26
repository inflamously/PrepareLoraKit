"""Image-embedding model catalog and loaders for the Curate step."""
from __future__ import annotations

from . import catalog
from .catalog import (
    AUTO,
    DEFAULT_CLIP_ID,
    EmbeddingModel,
    auto_select,
    clip_choices,
    coverage_choices,
    get,
    normalize_id,
)
from .vram import total_vram_gb

__all__ = [
    "catalog",
    "AUTO",
    "DEFAULT_CLIP_ID",
    "EmbeddingModel",
    "auto_select",
    "clip_choices",
    "coverage_choices",
    "get",
    "normalize_id",
    "total_vram_gb",
]
