"""Config schema for CurateStep."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class CurateConfig:
    """Config for CurateStep."""
    dedup_hamming_distance: int = 8
    occlusion_threshold: float = 0.35
    pca_umap_switch_threshold: int = 30
    umap_n_neighbors: int = 15
    umap_min_dist: float = 0.1
    pca_n_components: int = 2
    clip_model_id: str = "openai/clip-vit-base-patch32"
    skip_clip: bool = False

    def __post_init__(self) -> None:
        if not (0.0 <= self.occlusion_threshold <= 1.0):
            raise ValueError("CurateStep: occlusion_threshold must be in [0, 1]")
        if self.dedup_hamming_distance < 0:
            raise ValueError("CurateStep: dedup_hamming_distance must be >= 0")
