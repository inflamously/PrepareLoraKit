"""Editable config fields for CurateStep."""
from __future__ import annotations

from ....embedding import catalog
from ..fields import FieldSpec, _check, _number, _select

STEP_TYPE = "CurateStep"

FIELDS: list[FieldSpec] = [
    _number("dedup_hamming_distance", "Dedup hamming distance", "int", minimum=0, step=1),
    _number("occlusion_threshold", "Occlusion threshold", "float", minimum=0, maximum=1, step=0.05),
    _check("skip_clip", "Skip CLIP coverage"),
    _select("coverage_embedding_model", "Coverage embedding model",
            catalog.coverage_choices(), allow_custom=True,
            help="Embedding used for the coverage plot. Auto picks CLIP/DINOv2/Qwen by VRAM."),
    _select("clip_model_id", "CLIP model (occlusion)",
            catalog.clip_choices(), allow_custom=True,
            help="CLIP variant used for the zero-shot occlusion filter (needs text↔image)."),
    _number("pca_umap_switch_threshold", "PCA→UMAP switch", "int", minimum=0, step=1),
]
