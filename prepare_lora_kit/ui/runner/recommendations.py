"""Lightweight dataset prechecks that drive soft step-list recommendations.

These run on project load (via ``project_payload``) so the UI can softly
highlight a step the dataset would benefit from — currently the UpscaleStep,
when the dataset has images that are too small or carry JPEG artifacts.
"""
from __future__ import annotations

from pathlib import Path

from ...utils import image as img_utils

_JPEG_SUFFIXES = {".jpg", ".jpeg"}


def upscale_attention(dataset_dir: Path | None, threshold: int, cap: int = 5000) -> dict | None:
    """Decide whether the UpscaleStep should be recommended for ``dataset_dir``.

    Returns ``{"recommended", "undersized", "jpeg", "scanned"}`` or ``None`` when
    there is no readable dataset. ``undersized`` counts images whose short side is
    ``<= threshold``; ``jpeg`` counts JPEG-encoded images (compression artifacts).
    Recommendation fires when either count is non-zero.

    ``min_side`` is a header-only read (no pixel decode); ``cap`` bounds the number
    of per-image opens so project load stays snappy on very large folders.
    """
    if dataset_dir is None or not dataset_dir.is_dir():
        return None

    undersized = 0
    jpeg = 0
    scanned = 0
    for path in img_utils.iter_images(dataset_dir):
        if scanned >= cap:
            break
        scanned += 1
        if path.suffix.lower() in _JPEG_SUFFIXES:
            jpeg += 1
        try:
            if img_utils.min_side(path) <= threshold:
                undersized += 1
        except Exception:
            # A file that can't be read for size shouldn't break project load.
            continue

    return {
        "recommended": undersized > 0 or jpeg > 0,
        "undersized": undersized,
        "jpeg": jpeg,
        "scanned": scanned,
    }
