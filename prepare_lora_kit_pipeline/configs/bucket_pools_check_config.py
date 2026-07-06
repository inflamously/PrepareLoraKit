"""Config schema for BucketPoolsCheckStep."""
from __future__ import annotations
from dataclasses import dataclass, field


DEFAULT_RESOLUTION_BUCKETS: tuple[tuple[int, int], ...] = (
    (1024, 1024),
    (1152, 896),
    (896, 1152),
    (1216, 832),
    (832, 1216),
    (1344, 768),
    (768, 1344),
    (1536, 640),
    (640, 1536),
)


@dataclass
class BucketPoolsCheckConfig:
    """Config for BucketPoolsCheckStep."""
    thin_threshold: int = 2
    cache_mode: bool = False
    resolution_buckets: list[tuple[int, int]] = field(
        default_factory=lambda: list(DEFAULT_RESOLUTION_BUCKETS)
    )

    def __post_init__(self) -> None:
        if self.thin_threshold < 0:
            raise ValueError("BucketPoolsCheckStep: thin_threshold must be >= 0")
        self.resolution_buckets = [tuple(bucket) for bucket in self.resolution_buckets]
        if not self.resolution_buckets:
            raise ValueError("BucketPoolsCheckStep: resolution_buckets must not be empty")
        for bucket in self.resolution_buckets:
            if len(bucket) != 2 or bucket[0] < 1 or bucket[1] < 1:
                raise ValueError(
                    "BucketPoolsCheckStep: resolution_buckets entries must be positive width/height pairs"
                )
