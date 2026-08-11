"""Config schema for UpscaleStep."""
from __future__ import annotations

import warnings
from dataclasses import dataclass

from prepare_lora_kit.steps.upscale.seedvr2_adapter import SEEDVR2_MODEL_RESIDENCY_MODES
from prepare_lora_kit.steps.upscale.seedvr2_catalog import (
    AUTO as SEEDVR2_DIT_MODEL_AUTO,
)
from prepare_lora_kit.steps.upscale.seedvr2_catalog import (
    get_seedvr2_dit_model,
)


@dataclass
class UpscaleConfig:
    """Config for UpscaleStep."""
    upscale_target: int = 3072
    upscale_highlight_threshold: int = 1536
    hallucination_ssim_threshold: float = 0.60
    upscale_model: str = "seedvr2"
    seedvr2_submodule_dir: str | None = None
    seedvr2_model_dir: str | None = None
    seedvr2_dit_model: str | None = SEEDVR2_DIT_MODEL_AUTO
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
        self._normalize_upscale_model()
        self._normalize_seedvr2_dit_model()
        self._validate_ranges()

    def _normalize_upscale_model(self) -> None:
        """Fold the deprecated ``use_seedvr`` flag and ``seedvr`` spelling in."""
        # stacklevel=3: __post_init__ -> here, so the warning still points at the
        # caller that constructed the config rather than at this module.
        if self.use_seedvr is not None:
            warnings.warn(
                "UpscaleConfig.use_seedvr is deprecated; use upscale_model instead.",
                DeprecationWarning,
                stacklevel=3,
            )
            self.upscale_model = "seedvr2" if self.use_seedvr else "lanczos"
        if self.upscale_model == "seedvr":
            warnings.warn(
                "upscale_model=seedvr is deprecated; use upscale_model=seedvr2 instead.",
                DeprecationWarning,
                stacklevel=3,
            )
            self.upscale_model = "seedvr2"
        if self.upscale_model not in ("seedvr2", "lanczos", "custom"):
            raise ValueError(
                f"UpscaleStep: upscale_model must be seedvr2|lanczos|custom, "
                f"got '{self.upscale_model}'"
            )

    def _normalize_seedvr2_dit_model(self) -> None:
        """Default the DiT checkpoint, warning about ones outside the catalog.

        An unset value means ``auto``: the upscaler resolves it against the
        detected VRAM when the step runs (see ``seedvr2_adapter.prepare``).
        """
        if self.seedvr2_dit_model is not None:
            self.seedvr2_dit_model = str(self.seedvr2_dit_model).strip()
        if not self.seedvr2_dit_model:
            self.seedvr2_dit_model = SEEDVR2_DIT_MODEL_AUTO
        if (self.upscale_model == "seedvr2"
                and self.seedvr2_dit_model != SEEDVR2_DIT_MODEL_AUTO
                and get_seedvr2_dit_model(self.seedvr2_dit_model) is None):
            warnings.warn(
                "SeedVR2 DiT model "
                f"'{self.seedvr2_dit_model}' is not in PrepareLoraKit's supported catalog; "
                "continuing because local/custom checkpoints are allowed.",
                UserWarning,
                stacklevel=3,
            )

    def _validate_ranges(self) -> None:
        """Reject numeric settings that cannot produce a usable run."""
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
