"""Cache metadata writing for BucketPoolsCheckStep."""
from __future__ import annotations

import json
from pathlib import Path

from prepare_lora_kit.cancellation import CancelCheck, check_cancel
from prepare_lora_kit.report import reporter


def build_cache_info(
    bucket_map: dict[tuple[int, int], list[str]],
    *,
    display_name: str,
) -> dict:
    return {
        "bucket_source": display_name,
        "buckets": {
            f"{bw}x{bh}": paths
            for (bw, bh), paths in bucket_map.items()
            if paths
        },
    }


def write_cache_info(
    output_dir: Path,
    bucket_map: dict[tuple[int, int], list[str]],
    *,
    display_name: str,
    cancel_check: CancelCheck | None = None,
) -> dict:
    cache_info = build_cache_info(bucket_map, display_name=display_name)
    cache_path = output_dir / "cache_info.json"
    check_cancel(cancel_check)
    with open(cache_path, "w") as f:
        json.dump(cache_info, f, indent=2)
    reporter.ok(f"Cache info written → {cache_path}")
    return cache_info
