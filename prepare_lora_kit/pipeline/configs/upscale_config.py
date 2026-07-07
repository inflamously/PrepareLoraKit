"""Config schema for UpscaleStep."""
from __future__ import annotations
from dataclasses import dataclass
import warnings

from prepare_lora_kit.steps.upscale.seedvr2_catalog import DEFAULT_SEEDVR2_DIT_MODEL, get_seedvr2_dit_model
from prepare_lora_kit.steps.upscale.seedvr2_adapter import SEEDVR2_MODEL_RESIDENCY_MODES


@dataclass
class UpscaleConfig:
    """Config for UpscaleStep."""
    upscale_target: int = 3072
    upscale_highlight_threshold: int = 1536
    hallucination_ssim_threshold: float = 0.60
    upscale_model: str = "seedvr2"
    seedvr2_submodule_dir: str | None = None
    seedvr2_model_dir: str | None = None
    seedvr2_dit_model: str | None = DEFAULT_SEEDVR2_DIT_MODEL
    seedvr2_cuda_device: str | None = None
    seedvr2_batch_size: int = 1
    seedvr2_vae_tiled: bool = True
    seedvr2_cache_models: bool = True
    seedvr2_model_residency: str = "auto"
    seedvr2_debug: bool = False
    # Backward-compatible fields accepted from older project YAML. New configs
    # should use upscale_model + upscale_target only.
    use_seedvr: bool | None = None
    min_side_trigger: int | None = None

    def __post_init__(self) -> None:
        if self.use_seedvr is not None:
            warnings.warn(
                "UpscaleConfig.use_seedvr is deprecated; use upscale_model instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.upscale_model = "seedvr2" if self.use_seedvr else "lanczos"
        if self.upscale_model == "seedvr":
            warnings.warn(
                "upscale_model=seedvr is deprecated; use upscale_model=seedvr2 instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.upscale_model = "seedvr2"
        if self.upscale_model not in ("seedvr2", "lanczos", "custom"):
            raise ValueError(
                f"UpscaleStep: upscale_model must be seedvr2|lanczos|custom, got '{self.upscale_model}'"
            )
        if self.seedvr2_dit_model is not None:
            self.seedvr2_dit_model = str(self.seedvr2_dit_model).strip()
        if not self.seedvr2_dit_model:
            self.seedvr2_dit_model = DEFAULT_SEEDVR2_DIT_MODEL
        if self.upscale_model == "seedvr2" and get_seedvr2_dit_model(self.seedvr2_dit_model) is None:
            warnings.warn(
                "SeedVR2 DiT model "
                f"'{self.seedvr2_dit_model}' is not in PrepareLoraKit's supported catalog; "
                "continuing because local/custom checkpoints are allowed.",
                UserWarning,
                stacklevel=2,
            )
        if self.upscale_target <= 0:
            raise ValueError("UpscaleStep: upscale_target must be positive")
        if self.upscale_highlight_threshold <= 0:
            raise ValueError("UpscaleStep: upscale_highlight_threshold must be positive")
        if not (0.0 <= self.hallucination_ssim_threshold <= 1.0):
            raise ValueError("UpscaleStep: hallucination_ssim_threshold must be in [0, 1]")
        if self.seedvr2_batch_size <= 0:
            raise ValueError("UpscaleStep: seedvr2_batch_size must be positive")
        self.seedvr2_model_residency = str(self.seedvr2_model_residency or "auto").strip().lower()
        if self.seedvr2_model_residency not in SEEDVR2_MODEL_RESIDENCY_MODES:
            modes = "|".join(SEEDVR2_MODEL_RESIDENCY_MODES)
            raise ValueError(f"UpscaleStep: seedvr2_model_residency must be {modes}")
