"""Config schema for CaptionBboxStep."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class CaptionBboxConfig:
    """Config for CaptionBboxStep."""
    caption_model_id: str | None = None
    caption_model_task: str = "auto"     # auto | image-text-to-text | image-to-text
    caption_strategy: str = "grounded"   # grounded (observe→compose→verify) | single
    vram_tier: str = "auto"              # auto | low | mid | high | max
    max_new_tokens: int = 200
    spot_check_pct: float = 0.10
    qwen_model_id: str | None = None     # Legacy alias; use caption_model_id.
    # Optional custom prompt templates from the global prompt library. Blank/None
    # falls back to the built-in full-image / region defaults.
    caption_prompt: str | None = None
    region_prompt: str | None = None

    _VRAM_TIERS = {
        "auto": ("auto", "bfloat16"),
        "low":  ("4bit", "bfloat16"),   # <= 16 GB
        "mid":  ("8bit", "bfloat16"),   # <= 24 GB
        "high": ("none", "bfloat16"),   # <= 32 GB
        "max":  ("none", "bfloat16"),   # >= 32 GB
    }
    _MODEL_TASKS = {"auto", "image-text-to-text", "image-to-text"}
    _STRATEGIES = {"grounded", "single"}

    def __post_init__(self) -> None:
        if self.caption_model_id is not None:
            self.caption_model_id = str(self.caption_model_id).strip() or None
        if self.qwen_model_id is not None:
            self.qwen_model_id = str(self.qwen_model_id).strip() or None
        if self.caption_model_id is None and self.qwen_model_id:
            self.caption_model_id = self.qwen_model_id
        self.caption_model_task = str(self.caption_model_task or "auto").strip().lower()
        if self.caption_model_task not in self._MODEL_TASKS:
            raise ValueError(
                "CaptionBboxStep: caption_model_task must be one of "
                f"{list(self._MODEL_TASKS)}, got '{self.caption_model_task}'"
            )
        self.caption_strategy = str(self.caption_strategy or "grounded").strip().lower()
        if self.caption_strategy not in self._STRATEGIES:
            raise ValueError(
                "CaptionBboxStep: caption_strategy must be one of "
                f"{list(self._STRATEGIES)}, got '{self.caption_strategy}'"
            )
        if self.vram_tier not in self._VRAM_TIERS:
            raise ValueError(
                f"CaptionBboxStep: vram_tier must be one of {list(self._VRAM_TIERS)}, got '{self.vram_tier}'"
            )
        if not (0.0 <= self.spot_check_pct <= 1.0):
            raise ValueError("CaptionBboxStep: spot_check_pct must be in [0, 1]")
        self.caption_prompt = self._clean_prompt(self.caption_prompt)
        self.region_prompt = self._clean_prompt(self.region_prompt)

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
