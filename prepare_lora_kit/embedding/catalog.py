"""Image-embedding model catalog owned by PrepareLoraKit.

This module is the single source of truth for the embedding models offered in
the Curate step. Both the UI config schema (dropdown options) and the runtime
loaders read from here so the two can never drift apart.

Kept deliberately import-light: no ``torch``/``open_clip``/``transformers`` at
module load, so importing the config schema stays cheap.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingModel:
    """Metadata for one supported image-embedding model.

    ``id`` is the stable key stored in config and used as the dropdown value.
    For the ``clip`` family it doubles as the open_clip architecture name unless
    ``open_clip_name`` is set explicitly (e.g. DataComp/378px variants that share
    a base architecture but differ by pretrained weights).
    """

    id: str
    label: str
    family: str  # "clip" | "dinov2" | "qwen"
    dim: int
    min_vram_gb: float  # smallest card this is a sensible Auto pick for
    open_clip_name: str | None = None
    open_clip_pretrained: str | None = None
    hf_repo: str | None = None

    @property
    def arch(self) -> str:
        """open_clip architecture name (falls back to ``id`` for CLIP)."""
        return self.open_clip_name or self.id


# --- CLIP (open_clip) ------------------------------------------------------
# id == open_clip arch name unless open_clip_name overrides it.
CLIP_MODELS: tuple[EmbeddingModel, ...] = (
    EmbeddingModel("ViT-B-32", "CLIP ViT-B-32 (512d, fast)", "clip", 512, 0.0,
                   open_clip_pretrained="openai"),
    EmbeddingModel("ViT-B-16", "CLIP ViT-B-16 (512d)", "clip", 512, 0.0,
                   open_clip_pretrained="openai"),
    EmbeddingModel("ViT-B-16-plus-240", "CLIP ViT-B-16-plus-240 (640d)", "clip", 640, 6.0,
                   open_clip_pretrained="laion400m_e32"),
    EmbeddingModel("ViT-L-14", "CLIP ViT-L-14 (768d)", "clip", 768, 8.0,
                   open_clip_pretrained="openai"),
    EmbeddingModel("ViT-L-14-336", "CLIP ViT-L-14-336 (768d, 336px)", "clip", 768, 10.0,
                   open_clip_pretrained="openai"),
    EmbeddingModel("ViT-L-14-datacomp", "CLIP ViT-L-14 DataComp-XL (768d)", "clip", 768, 8.0,
                   open_clip_name="ViT-L-14", open_clip_pretrained="datacomp_xl_s13b_b90k"),
    EmbeddingModel("ViT-H-14", "CLIP ViT-H-14 (1024d)", "clip", 1024, 12.0,
                   open_clip_pretrained="laion2b_s32b_b79k"),
    EmbeddingModel("ViT-H-14-378", "CLIP ViT-H-14-378 (1024d, 378px)", "clip", 1024, 16.0,
                   open_clip_name="ViT-H-14-378-quickgelu", open_clip_pretrained="dfn5b"),
    EmbeddingModel("ViT-g-14", "CLIP ViT-g-14 (1024d, giant)", "clip", 1024, 16.0,
                   open_clip_pretrained="laion2b_s12b_b42k"),
    EmbeddingModel("ViT-bigG-14", "CLIP ViT-bigG-14 (1280d, largest)", "clip", 1280, 24.0,
                   open_clip_pretrained="laion2b_s39b_b160k"),
    EmbeddingModel("convnext_base_w", "CLIP ConvNeXt-Base-W (512d, CNN)", "clip", 512, 0.0,
                   open_clip_pretrained="laion2b_s13b_b82k_augreg"),
    EmbeddingModel("convnext_large_d_320", "CLIP ConvNeXt-Large-D 320 (768d)", "clip", 768, 8.0,
                   open_clip_pretrained="laion2b_s29b_b131k_ft_soup"),
)

# --- DINOv2 (transformers) -------------------------------------------------
DINOV2_MODELS: tuple[EmbeddingModel, ...] = (
    EmbeddingModel("facebook/dinov2-small", "DINOv2 small (384d)", "dinov2", 384, 0.0,
                   hf_repo="facebook/dinov2-small"),
    EmbeddingModel("facebook/dinov2-base", "DINOv2 base (768d)", "dinov2", 768, 6.0,
                   hf_repo="facebook/dinov2-base"),
)

# --- Qwen3-VL embedding (sentence-transformers) ----------------------------
# Causal-LM-based multimodal embedding models, loaded via sentence-transformers
# (see loaders._embed_qwen). This catalog is the one place to add/fix repo ids.
QWEN_MODELS: tuple[EmbeddingModel, ...] = (
    EmbeddingModel("Qwen/Qwen3-VL-Embedding-2B", "Qwen3-VL Embedding 2B (2048d)", "qwen", 2048, 24.0,
                   hf_repo="Qwen/Qwen3-VL-Embedding-2B"),
    EmbeddingModel("Qwen/Qwen3-VL-Embedding-8B", "Qwen3-VL Embedding 8B (2048d, best)", "qwen", 2048, 32.0,
                   hf_repo="Qwen/Qwen3-VL-Embedding-8B"),
)

COVERAGE_MODELS: tuple[EmbeddingModel, ...] = CLIP_MODELS + DINOV2_MODELS + QWEN_MODELS

_BY_ID: dict[str, EmbeddingModel] = {m.id: m for m in COVERAGE_MODELS}

# Legacy/alias ids → canonical catalog id. Projects saved before the open_clip
# switch stored the Hugging Face repo string for clip_model_id.
_ALIASES: dict[str, str] = {
    "openai/clip-vit-base-patch32": "ViT-B-32",
    "openai/clip-vit-base-patch16": "ViT-B-16",
    "openai/clip-vit-large-patch14": "ViT-L-14",
    "openai/clip-vit-large-patch14-336": "ViT-L-14-336",
}

AUTO = "auto"
DEFAULT_CLIP_ID = "ViT-B-32"

__all__ = [
    "EmbeddingModel",
    "CLIP_MODELS",
    "DINOV2_MODELS",
    "QWEN_MODELS",
    "COVERAGE_MODELS",
    "AUTO",
    "DEFAULT_CLIP_ID",
    "normalize_id",
    "get",
    "coverage_choices",
    "clip_choices",
    "auto_select",
]


def normalize_id(model_id: str | None) -> str:
    """Map legacy/alias ids to their canonical catalog id (identity otherwise)."""
    if not model_id:
        return DEFAULT_CLIP_ID
    return _ALIASES.get(model_id, model_id)


def get(model_id: str) -> EmbeddingModel | None:
    """Return catalog metadata for a model id, or ``None`` if it's custom/unknown."""
    return _BY_ID.get(normalize_id(model_id))


def coverage_choices() -> list[tuple[str, str]]:
    """``(value, label)`` pairs for the coverage-embedding dropdown (Auto first)."""
    return [(AUTO, "Auto (match VRAM)")] + [(m.id, m.label) for m in COVERAGE_MODELS]


def clip_choices() -> list[tuple[str, str]]:
    """``(value, label)`` pairs for the occlusion CLIP dropdown (CLIP only)."""
    return [(m.id, m.label) for m in CLIP_MODELS]


def auto_select(total_vram_gb: float) -> str:
    """Pick the best coverage-embedding id for the available VRAM.

    Ladder (thresholds are deliberately conservative and easy to tune):
      * no CUDA / <=16 GB  -> CLIP ViT-B-32   (512d, light)
      * <=24 GB            -> DINOv2 base     (768d)
      * <=32 GB            -> Qwen3-VL 2B      (2048d)
      * >32 GB             -> Qwen3-VL 8B      (2048d, best)
    """
    gb = float(total_vram_gb or 0.0)
    if gb <= 16:
        return "ViT-B-32"
    if gb <= 24:
        return "facebook/dinov2-base"
    if gb <= 32:
        return "Qwen/Qwen3-VL-Embedding-2B"
    return "Qwen/Qwen3-VL-Embedding-8B"
