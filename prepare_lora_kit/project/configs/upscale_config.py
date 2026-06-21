"""Config schema for UpscaleStep."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class UpscaleConfig:
    """Config for UpscaleStep."""
    upscale_target: int = 3072
    hallucination_ssim_threshold: float = 0.60
    upscale_model: str = "seedvr"
    # Backward-compatible fields accepted from older project YAML. New configs
    # should use upscale_model + upscale_target only.
    use_seedvr: bool | None = None
    min_side_trigger: int | None = None

    def __post_init__(self) -> None:
        if self.upscale_model not in ("seedvr", "lanczos", "custom"):
            raise ValueError(
                f"UpscaleStep: upscale_model must be seedvr|lanczos|custom, got '{self.upscale_model}'"
            )
        if self.upscale_target <= 0:
            raise ValueError("UpscaleStep: upscale_target must be positive")
        if not (0.0 <= self.hallucination_ssim_threshold <= 1.0):
            raise ValueError("UpscaleStep: hallucination_ssim_threshold must be in [0, 1]")
