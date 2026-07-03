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

    def __post_init__(self) -> None:
        if self.min_caption >= self.max_caption:
            raise ValueError("AuditStep: min_caption must be < max_caption")
