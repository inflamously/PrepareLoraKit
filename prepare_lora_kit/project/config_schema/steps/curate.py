"""Editable config fields for CurateStep."""
from __future__ import annotations

from ..fields import FieldSpec, _check, _number, _text

STEP_TYPE = "CurateStep"

FIELDS: list[FieldSpec] = [
    _number("dedup_hamming_distance", "Dedup hamming distance", "int", minimum=0, step=1),
    _number("occlusion_threshold", "Occlusion threshold", "float", minimum=0, maximum=1, step=0.05),
    _check("skip_clip", "Skip CLIP coverage"),
    _text("clip_model_id", "CLIP model id", placeholder="openai/clip-vit-base-patch32"),
    _number("pca_umap_switch_threshold", "PCA→UMAP switch", "int", minimum=0, step=1),
]
