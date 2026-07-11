"""Config schema for VaeGateStep."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class VaeGateConfig:
    """Config for VaeGateStep."""
    vae_model_id: str = "black-forest-labs/FLUX.2-klein-base-9B"
    vae_config_id: Optional[str] = None
    diff_amplification: float = 4.0
    gaussian_blur_sigma: float = 2.0
    gaussian_blur_kernel: int = 21
    otsu_enabled: bool = True
    output_previews: bool = True
    output_silhouettes: bool = True
    output_hard_silhouettes: bool = True
    outlier_sigma: float = 2.0
    hf_cutoff_fraction: float = 0.25
    max_side: Optional[int] = 1536
    seed: int = 42

    def __post_init__(self) -> None:
        if not self.vae_model_id:
            raise ValueError("VaeGateStep: vae_model_id is required")
        if self.diff_amplification < 0:
            raise ValueError("VaeGateStep: diff_amplification must be >= 0")
        if self.gaussian_blur_sigma < 0:
            raise ValueError("VaeGateStep: gaussian_blur_sigma must be >= 0")
        if self.gaussian_blur_kernel < 1 or self.gaussian_blur_kernel % 2 == 0:
            raise ValueError("VaeGateStep: gaussian_blur_kernel must be a positive odd number")
        if self.outlier_sigma < 0:
            raise ValueError("VaeGateStep: outlier_sigma must be >= 0")
        if not (0.0 < self.hf_cutoff_fraction < 0.5):
            raise ValueError("VaeGateStep: hf_cutoff_fraction must be in (0, 0.5)")
        if self.max_side is not None and self.max_side < 8:
            raise ValueError("VaeGateStep: max_side must be >= 8 when set")
