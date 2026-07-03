"""Config schema for BucketDryRunStep."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class BucketDryRunConfig:
    """Config for BucketDryRunStep."""
    thin_threshold: int = 2
    cache_mode: bool = False
    bucket_overrides: Optional[list[tuple[int, int]]] = None

    def __post_init__(self) -> None:
        if self.thin_threshold < 0:
            raise ValueError("BucketDryRunStep: thin_threshold must be >= 0")
