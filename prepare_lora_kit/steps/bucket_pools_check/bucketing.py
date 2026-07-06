"""
Bucketing helpers for Step 8.

Aspect-ratio math and bucket assignment / crop-suggestion utilities used by the
bucket dry-run step.
"""
from __future__ import annotations
import math


def _aspect(w: int, h: int) -> float:
    return w / h


def _bucket_distance(img_w: int, img_h: int, bw: int, bh: int) -> float:
    img_ar = _aspect(img_w, img_h)
    bkt_ar = _aspect(bw, bh)
    return abs(math.log(img_ar) - math.log(bkt_ar))


def _find_bucket(img_w: int, img_h: int, buckets: list[tuple[int, int]]) -> tuple[int, int]:
    return min(buckets, key=lambda b: _bucket_distance(img_w, img_h, b[0], b[1]))


def _suggest_crop(img_w: int, img_h: int, bw: int, bh: int) -> str:
    target_ar = bw / bh
    if img_w / img_h > target_ar:
        new_w = int(img_h * target_ar)
        return f"centre-crop width to {new_w}px (from {img_w}px)"
    else:
        new_h = int(img_w / target_ar)
        return f"centre-crop height to {new_h}px (from {img_h}px)"
