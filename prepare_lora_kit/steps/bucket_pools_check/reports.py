"""Report payload helpers for BucketPoolsCheckStep."""
from __future__ import annotations


def substep_status(enabled: set[str]) -> dict[str, dict[str, bool]]:
    return {
        "assign_bucket_pools": {"enabled": "assign_bucket_pools" in enabled},
        "report_thin_buckets": {"enabled": "report_thin_buckets" in enabled},
        "write_cache_info": {"enabled": "write_cache_info" in enabled},
    }


def build_skipped_report(
    enabled: set[str],
    *,
    thin_threshold: int,
    reason: str = "assign_bucket_pools disabled",
) -> dict:
    """A no-work report with the same key set as a successful one.

    ``substeps`` reports what was *enabled*, not what happened: an empty dataset
    skips substeps that were switched on, and saying they were off would be a
    second, wronger story than the one ``reason`` already tells.
    """
    return {
        "skipped": True,
        "reason": reason,
        "buckets": {},
        "thin_buckets": [],
        "thin_threshold": thin_threshold,
        "cache_mode": False,
        "substeps": substep_status(enabled),
    }


def build_success_report(
    bucket_map: dict[tuple[int, int], list[str]],
    *,
    thin_buckets: list[dict],
    thin_threshold: int,
    cache_mode: bool,
    enabled: set[str],
) -> dict:
    return {
        "buckets": {
            f"{bw}x{bh}": {"count": len(paths), "paths": paths}
            for (bw, bh), paths in bucket_map.items()
        },
        "thin_buckets": thin_buckets,
        "thin_threshold": thin_threshold,
        "cache_mode": cache_mode and "write_cache_info" in enabled,
        "substeps": substep_status(enabled),
    }
