"""CLIP coverage and occlusion scan substep."""
from __future__ import annotations

from ..coverage import _clip_embeddings, _save_pca, _save_umap
from ..occlusion import OCCLUSION_THRESHOLD, _occlusion_scores

__all__ = [
    "OCCLUSION_THRESHOLD",
    "_clip_embeddings",
    "_occlusion_scores",
    "_save_pca",
    "_save_umap",
]
