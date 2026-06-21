"""Config schema for CaptionStep."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class CaptionConfig:
    """Config for CaptionStep."""
    qwen_model_id: str = "Qwen/Qwen2-VL-7B-Instruct"
    vram_tier: str = "auto"              # auto | low | mid | high | max
    max_new_tokens: int = 200
    spot_check_pct: float = 0.10

    _VRAM_TIERS = {
        "auto": ("auto", "bfloat16"),
        "low":  ("4bit", "bfloat16"),   # <= 16 GB
        "mid":  ("8bit", "bfloat16"),   # <= 24 GB
        "high": ("none", "bfloat16"),   # <= 32 GB
        "max":  ("none", "bfloat16"),   # >= 32 GB
    }

    def __post_init__(self) -> None:
        if self.vram_tier not in self._VRAM_TIERS:
            raise ValueError(
                f"CaptionStep: vram_tier must be one of {list(self._VRAM_TIERS)}, got '{self.vram_tier}'"
            )
        if not (0.0 <= self.spot_check_pct <= 1.0):
            raise ValueError("CaptionStep: spot_check_pct must be in [0, 1]")

    @property
    def quantization(self) -> str:
        return self._VRAM_TIERS[self.vram_tier][0]

    @property
    def dtype(self) -> str:
        return self._VRAM_TIERS[self.vram_tier][1]
