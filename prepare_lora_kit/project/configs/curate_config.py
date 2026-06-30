"""Config schema for CurateStep."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class CurateConfig:
    """Config for CurateStep."""
    dedup_hamming_distance: int = 3
    pca_umap_switch_threshold: int = 30
    umap_n_neighbors: int = 15
    umap_min_dist: float = 0.1
    pca_n_components: int = 2
    coverage_embedding_model: str = "auto"
    skip_clip: bool = False

    def __post_init__(self) -> None:
        if self.dedup_hamming_distance < 0:
            raise ValueError("CurateStep: dedup_hamming_distance must be >= 0")
