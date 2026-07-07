"""Report payload helpers for BucketPoolsCheckStep."""
from __future__ import annotations


def substep_status(enabled: set[str]) -> dict[str, dict[str, bool]]:
    return {
        "assign_bucket_pools": {"enabled": "assign_bucket_pools" in enabled},
        "report_thin_buckets": {"enabled": "report_thin_buckets" in enabled},
        "write_cache_info": {"enabled": "write_cache_info" in enabled},
    }


def build_skipped_report(enabled: set[str]) -> dict:
    return {
        "skipped": True,
        "reason": "assign_bucket_pools disabled",
        "buckets": {},
        "thin_buckets": [],
        "cache_mode": False,
        "substeps": {
            "assign_bucket_pools": {"enabled": False},
            "report_thin_buckets": {"enabled": "report_thin_buckets" in enabled},
            "write_cache_info": {"enabled": "write_cache_info" in enabled},
        },
    }


def build_success_report(
    bucket_map: dict[tuple[int, int], list[str]],
    *,
    thin_buckets: list[dict],
    cache_mode: bool,
    enabled: set[str],
) -> dict:
    return {
        "buckets": {
            f"{bw}x{bh}": {"count": len(paths), "paths": paths}
            for (bw, bh), paths in bucket_map.items()
        },
        "thin_buckets": thin_buckets,
        "cache_mode": cache_mode and "write_cache_info" in enabled,
        "substeps": substep_status(enabled),
    }
