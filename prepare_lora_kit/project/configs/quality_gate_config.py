"""Config schema for QualityGateStep."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScorerEntry:
    name: str
    enabled: bool = True
    op: str = "lt"                       # "lt" | "gt"
    threshold: float = 0.0
    borderline: Optional[float] = None   # triggers manual review even on pass


@dataclass
class QualityGateConfig:
    """Config for QualityGateStep."""
    scorers: list[ScorerEntry] = field(default_factory=lambda: [
        ScorerEntry(name="min_side",  op="lt", threshold=1024.0),
        ScorerEntry(name="blur",      op="lt", threshold=100.0, borderline=150.0),
        ScorerEntry(name="noise",     op="gt", threshold=25.0),
        ScorerEntry(name="jpeg",      op="gt", threshold=0.08),
        ScorerEntry(name="watermark", op="gt", threshold=0.80),
    ])
    manual_review: bool = True
    auto_only: bool = False
    manual_all: bool = False

    def __post_init__(self) -> None:
        for s in self.scorers:
            if s.op not in ("lt", "gt"):
                raise ValueError(
                    f"QualityGateStep scorer '{s.name}': op must be 'lt' or 'gt', got '{s.op}'"
                )
        if self.auto_only and self.manual_all:
            raise ValueError("QualityGateStep: auto_only and manual_all are mutually exclusive")
