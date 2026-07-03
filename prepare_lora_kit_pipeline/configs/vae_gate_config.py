"""Config schema for VaeGateStep."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class VaeGateConfig:
    """Config for VaeGateStep."""
    diff_amplification: float = 4.0
    gaussian_blur_sigma: float = 2.0
    gaussian_blur_kernel: int = 21
    otsu_enabled: bool = True
    output_previews: bool = True
    output_silhouettes: bool = True
    output_hard_silhouettes: bool = True
    outlier_sigma: float = 2.0
    hf_cutoff_fraction: float = 0.25
    max_side: Optional[int] = None
    seed: int = 42

    def __post_init__(self) -> None:
        if self.gaussian_blur_kernel % 2 == 0:
            raise ValueError("VaeGateStep: gaussian_blur_kernel must be odd")
        if not (0.0 < self.hf_cutoff_fraction < 0.5):
            raise ValueError("VaeGateStep: hf_cutoff_fraction must be in (0, 0.5)")
