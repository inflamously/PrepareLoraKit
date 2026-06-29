from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import yaml


@dataclass
class NetworkProfile:
    """Base-model profile: model id, VAE, scheduler, buckets, lr/rank ranges, and a
    config_template merged into the ai-toolkit training YAML.

    NOTE: this describes the *base model*, not the trainable adapter. The adapter
    network (lora/lokr/dora) is ``NetworkConfig`` in ``config.py``; its block lives
    under ``config_template.network`` here.
    """
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
    # Optional config source for single-file VAEs (``vae_model_id`` pointing at a bare
    # checkpoint). Points at a base repo whose ``vae/`` config matches the architecture; only
    # needed when diffusers cannot infer the config from the checkpoint's state-dict keys.
    vae_config_id: str | None = None
    # effective_rank = alpha / rank; ratio outside this range triggers a warning
    lr_alpha_rank_ratio_range: tuple[float, float] = (0.5, 2.0)
    requires_diff_guidance: bool = False
    # Base pixel-budget sides emitted to ai-toolkit datasets[].resolution.
    # Empty → step 7 falls back to [max_bucket_side].
    train_resolutions: list[int] = field(default_factory=list)

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
