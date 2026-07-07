"""Config schema for AuditStep."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class AuditConfig:
    """Config for AuditStep."""
    min_caption: int = 5
    max_caption: int = 600
    check_pairing: bool = True
    check_corrupt: bool = True
    check_caption_length: bool = True
    check_resolution_gate: bool = True
    min_resolution_side: int | None = 1536
    caption_model_type: str = "auto"

    def __post_init__(self) -> None:
        if self.min_caption >= self.max_caption:
            raise ValueError("AuditStep: min_caption must be < max_caption")
        if self.min_resolution_side is not None and self.min_resolution_side < 1:
            raise ValueError("AuditStep: min_resolution_side must be >= 1 when set")
