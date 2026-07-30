"""Config schema for CaptionVerifierStep."""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import ClassVar

from prepare_lora_kit.steps.caption_verifier import catalog


@dataclass
class CaptionVerifierConfig:
    """Config for CaptionVerifierStep.

    The step renders each caption with a text-to-image model so the user can
    see what the text encoder actually understood. ``None`` on a generation
    parameter means "use the selected model family's default" — a single
    hard-coded value cannot serve SD 1.5 (512px/30 steps/cfg 7.5) and a
    step-distilled model (1024px/8 steps/cfg 1.0) at once.
    """

    t2i_model_id: str = "auto"  # "auto" | catalog id | repo id | .safetensors path
    vram_tier: str = "auto"  # auto | low | mid | high | max
    width: int | None = None
    height: int | None = None
    num_inference_steps: int | None = None
    guidance_scale: float | None = None
    seed: int = 42
    negative_prompt: str | None = None  # ignored by the FLUX / Krea families
    max_images: int | None = None
    keep_previews: bool = True
    write_edited_captions: bool = True

    # -> (quantization, dtype, offload). ``low``/``mid`` share a strategy; what
    # differs between them is the *model* ``catalog.auto_select`` picks. No tier
    # names "sequential": that escalation is decided at runtime from actual free
    # VRAM, which also keeps the forbidden 4bit+sequential pair out of the table.
    _VRAM_TIERS: ClassVar[dict[str, tuple[str, str, str]]] = {
        "auto": ("auto", "bfloat16", "auto"),
        "low": ("4bit", "bfloat16", "model"),   # <= 16 GB
        "mid": ("4bit", "bfloat16", "model"),   # <= 24 GB
        "high": ("none", "bfloat16", "model"),  # <= 32 GB
        "max": ("none", "bfloat16", "none"),    # >  32 GB
    }

    def __post_init__(self) -> None:
        self.t2i_model_id = catalog.normalize_id(self.t2i_model_id)
        if self.t2i_model_id != catalog.AUTO and catalog.get(self.t2i_model_id) is None:
            # Custom ids are the point of allow_custom; warn, do not reject.
            warnings.warn(
                f"CaptionVerifierStep: '{self.t2i_model_id}' is not a known "
                "text-to-image model; it will be loaded via the diffusers auto "
                "pipeline with conservative defaults.",
                UserWarning,
                stacklevel=2,
            )

        self.vram_tier = str(self.vram_tier or "auto").strip().lower()
        if self.vram_tier not in self._VRAM_TIERS:
            raise ValueError(
                "CaptionVerifierStep: vram_tier must be one of "
                f"{list(self._VRAM_TIERS)}, got '{self.vram_tier}'"
            )

        self.width = self._dimension(self.width, "width")
        self.height = self._dimension(self.height, "height")

        if self.num_inference_steps is not None:
            self.num_inference_steps = int(self.num_inference_steps)
            if not (1 <= self.num_inference_steps <= 150):
                raise ValueError(
                    "CaptionVerifierStep: num_inference_steps must be in [1, 150]"
                )

        if self.guidance_scale is not None:
            self.guidance_scale = float(self.guidance_scale)
            if not (0.0 <= self.guidance_scale <= 30.0):
                raise ValueError(
                    "CaptionVerifierStep: guidance_scale must be in [0, 30]"
                )

        self.seed = int(self.seed)
        if not (0 <= self.seed < 2 ** 32):
            raise ValueError("CaptionVerifierStep: seed must be in [0, 2**32)")

        if self.max_images is not None:
            self.max_images = int(self.max_images)
            if self.max_images < 1:
                raise ValueError("CaptionVerifierStep: max_images must be >= 1")

        self.negative_prompt = self._clean_prompt(self.negative_prompt)
        self.keep_previews = bool(self.keep_previews)
        self.write_edited_captions = bool(self.write_edited_captions)

    @staticmethod
    def _dimension(value: int | None, label: str) -> int | None:
        if value is None:
            return None
        size = int(value)
        if not (256 <= size <= 4096):
            raise ValueError(
                f"CaptionVerifierStep: {label} must be in [256, 4096], got {size}"
            )
        if size % 8:
            raise ValueError(
                f"CaptionVerifierStep: {label} must be a multiple of 8, got {size}"
            )
        return size

    @staticmethod
    def _clean_prompt(value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip() or None

    @property
    def quantization(self) -> str:
        return self._VRAM_TIERS[self.vram_tier][0]

    @property
    def dtype(self) -> str:
        return self._VRAM_TIERS[self.vram_tier][1]

    @property
    def offload(self) -> str:
        return self._VRAM_TIERS[self.vram_tier][2]
