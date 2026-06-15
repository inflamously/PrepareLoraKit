from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import yaml


@dataclass
class NetworkProfile:
    name: str
    display_name: str
    resolution_buckets: list[tuple[int, int]]
    max_pixels: int
    vae_model_id: str
    lr_range: tuple[float, float]
    rank_range: tuple[int, int]
    model_type: str
    noise_scheduler: str
    config_template: dict[str, Any] = field(default_factory=dict)
    # effective_rank = alpha / rank; ratio outside this range triggers a warning
    lr_alpha_rank_ratio_range: tuple[float, float] = (0.5, 2.0)
    requires_diff_guidance: bool = False

    @property
    def max_bucket_side(self) -> int:
        return max(max(w, h) for w, h in self.resolution_buckets)

    @classmethod
    def from_yaml(cls, path: Path) -> "NetworkProfile":
        with open(path) as f:
            data = yaml.safe_load(f)
        buckets = [tuple(b) for b in data.pop("resolution_buckets")]
        lr_range = tuple(data.pop("lr_range"))
        rank_range = tuple(data.pop("rank_range"))
        ratio_range = tuple(data.pop("lr_alpha_rank_ratio_range", [0.5, 2.0]))
        return cls(
            resolution_buckets=buckets,
            lr_range=lr_range,
            rank_range=rank_range,
            lr_alpha_rank_ratio_range=ratio_range,
            **data,
        )
