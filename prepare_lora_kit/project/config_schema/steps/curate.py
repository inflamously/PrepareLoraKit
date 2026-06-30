"""Editable config fields for CurateStep."""
from __future__ import annotations

from ....embedding import catalog
from ..fields import FieldSpec, _check, _number, _select

STEP_TYPE = "CurateStep"

FIELDS: list[FieldSpec] = [
    _number("dedup_hamming_distance", "Dedup hamming distance", "int", minimum=0, step=1),
    _check("skip_clip", "Skip CLIP coverage"),
    _select("coverage_embedding_model", "Coverage embedding model",
            catalog.coverage_choices(), allow_custom=True,
            help="Embedding used for the coverage plot. Auto picks CLIP/DINOv2/Qwen by VRAM."),
    _number("pca_umap_switch_threshold", "PCA→UMAP switch", "int", minimum=0, step=1),
]
