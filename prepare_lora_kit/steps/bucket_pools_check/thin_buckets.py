"""Thin-bucket analysis for BucketPoolsCheckStep."""
from __future__ import annotations

from PIL import Image

from prepare_lora_kit.cancellation import CancelCheck, cancellable, noop_cancel_check
from prepare_lora_kit.steps.bucket_pools_check.bucketing import _suggest_crop


def collect_thin_buckets(
    bucket_map: dict[tuple[int, int], list[str]],
    *,
    thin_threshold: int,
    cancel_check: CancelCheck = noop_cancel_check,
) -> list[dict]:
    thin_buckets: list[dict] = []

    for bucket, paths in cancellable(sorted(bucket_map.items()), cancel_check):
        n = len(paths)
        if n == 0 or n > thin_threshold:
            continue

        suggestions = []
        for path in cancellable(paths, cancel_check):
            with Image.open(path) as img:
                iw, ih = img.size
            suggestions.append(_suggest_crop(iw, ih, bucket[0], bucket[1]))

        suggestion = "; ".join(dict.fromkeys(suggestions))
        thin_buckets.append(
            {
                "bucket": list(bucket),
                "count": n,
                "paths": paths,
                "suggestion": suggestion,
            }
        )

    return thin_buckets
