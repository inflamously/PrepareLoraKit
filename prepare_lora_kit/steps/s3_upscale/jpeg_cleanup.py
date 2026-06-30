"""Shared helpers for cleaning up JPEG compression artifacts during Step 3.

JPEG block/ringing artifacts are baked in at the file's original encoding
resolution, so a plain resize (up or down) just rescales the artifacts along
with the image content. These helpers either denoise in place (for the
non-AI Lanczos path) or shrink the image enough to shed the artifacts before
an AI upscaler regrows the resolution.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

JPEG_EXTS = (".jpg", ".jpeg")


def _is_jpeg(path: Path) -> bool:
    return path.suffix.lower() in JPEG_EXTS


def _downscale_divisor(min_side: int, target: int = 1024) -> int:
    """Pick 2 or 3, whichever lands min_side / divisor closest to target."""
    return min((2, 3), key=lambda d: abs(min_side / d - target))


def _denoise(img):
    """Gently reduce JPEG block/ringing artifacts in a PIL RGB image.

    Used on the Lanczos path, which has no learned restoration of its own.
    SeedVR2 already reduces compression artifacts as a side effect of its
    generative upscaling, so callers should skip this for that path.

    The denoise strength is deliberately mild (luminance/chroma ``h=3``): strong
    NL-means values visibly soften fine detail, which matters for training data,
    so this only smooths blocking/ringing rather than scrubbing texture.
    """
    import cv2
    import numpy as np
    from PIL import Image

    arr = np.array(img.convert("RGB"))
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    denoised = cv2.fastNlMeansDenoisingColored(bgr, None, 3, 3, 7, 21)
    return Image.fromarray(cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB))


def _scratch_name(path: Path, suffix: str) -> str:
    """Collision-proof scratch filename: same-stem files in different subdirs
    must not map to the same flat scratch path."""
    digest = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:8]
    return f"{path.stem}.{digest}{suffix}"


def _write_downscaled_copy(path: Path, scratch_dir: Path) -> Path:
    """Shrink a JPEG toward ~1024px short side and save as PNG in scratch_dir.

    Saving as PNG (rather than re-encoding as JPEG) avoids baking in a fresh
    round of compression artifacts before the upscaler regrows the image.
    """
    from PIL import Image

    scratch_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(path) as img:
        img = img.convert("RGB")
        w, h = img.size
        divisor = _downscale_divisor(min(w, h))
        new_w, new_h = max(1, w // divisor), max(1, h // divisor)
        small = img.resize((new_w, new_h), Image.LANCZOS)
    out_path = scratch_dir / _scratch_name(path, ".predownscale.png")
    small.save(out_path)
    return out_path
