from __future__ import annotations
from pathlib import Path


from prepare_lora_kit.utils import image as img_utils
HALLUCINATION_SSIM_THRESHOLD = 0.60   # low-freq SSIM; below = possible hallucination


def _hallucination_check(original: Path, upscaled: Path) -> float:
    """
    Compare low-frequency content of original vs upscaled via SSIM.
    Returns SSIM score; below threshold suggests hallucinated detail.
    """
    import cv2
    import numpy as np
    from skimage.metrics import structural_similarity as ssim

    orig = cv2.cvtColor(img_utils.load_cv2(original), cv2.COLOR_BGR2GRAY).astype(np.float32)
    up = cv2.cvtColor(img_utils.load_cv2(upscaled), cv2.COLOR_BGR2GRAY).astype(np.float32)

    # Resize orig to match upscaled
    up_h, up_w = up.shape
    orig_resized = cv2.resize(orig, (up_w, up_h), interpolation=cv2.INTER_LANCZOS4)

    # Blur both to compare only low-freq content
    blur_orig = cv2.GaussianBlur(orig_resized, (21, 21), 0)
    blur_up = cv2.GaussianBlur(up, (21, 21), 0)

    return float(ssim(blur_orig, blur_up, data_range=255))
