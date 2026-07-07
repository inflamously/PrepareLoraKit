"""Image-to-bucket assignment helpers for BucketPoolsCheckStep."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from prepare_lora_kit.cancellation import CancelCheck, check_cancel
from prepare_lora_kit.report import reporter
from prepare_lora_kit.steps.bucket_pools_check.bucketing import _find_bucket


def assign_bucket_pools(
    images: list[Path],
    resolution_buckets: list[tuple[int, int]],
    *,
    cancel_check: CancelCheck | None = None,
) -> dict[tuple[int, int], list[str]]:
    buckets = [tuple(bucket) for bucket in resolution_buckets]
    bucket_map: dict[tuple[int, int], list[str]] = {bucket: [] for bucket in buckets}

    for path in images:
        check_cancel(cancel_check)
        try:
            with Image.open(path) as img:
                iw, ih = img.size
        except Exception as exc:
            reporter.warn(f"Could not read {path.name}: {exc}")
            continue

        best = _find_bucket(iw, ih, buckets)
        bucket_map[best].append(str(path))

    return bucket_map
