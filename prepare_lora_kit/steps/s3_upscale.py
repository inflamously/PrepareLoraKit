"""
Step 3 — Upscale (optional)

Selectively upscales images below the target min-side.
SeedVR is the default upscaler; falls back to Lanczos (PIL) if SEEDVR_PATH is unset.
Re-runs Step 1 quality checks post-upscale to reject hallucinated-texture outputs.
"""
from __future__ import annotations
import os
import subprocess
from pathlib import Path
from typing import Callable

from ..utils import image as img_utils
from ..utils import report as rpt

UPSCALE_TARGET = 1024
HALLUCINATION_SSIM_THRESHOLD = 0.60   # low-freq SSIM; below = possible hallucination


def _seedvr_upscale(path: Path, output_path: Path) -> Path:
    seedvr = os.environ.get("SEEDVR_PATH", "")
    if not seedvr:
        raise RuntimeError("SEEDVR_PATH env var not set")
    cmd = [
        "python", str(seedvr),
        "--input", str(path),
        "--output", str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"SeedVR failed: {result.stderr[:500]}")
    return output_path


def _lanczos_upscale(path: Path, output_path: Path, target: int = UPSCALE_TARGET) -> Path:
    from PIL import Image
    img = Image.open(path).convert("RGB")
    w, h = img.size
    ms = min(w, h)
    scale = target / ms
    new_w, new_h = int(w * scale), int(h * scale)
    up = img.resize((new_w, new_h), Image.LANCZOS)
    up.save(output_path)
    return output_path


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


def run(
    dataset_dir: Path,
    output_dir: Path | None = None,
    upscale_target: int = UPSCALE_TARGET,
    upscaler: Callable[[Path, Path], Path] | None = None,
    use_seedvr: bool = True,
) -> dict:
    rpt.step_header(3, "Upscale (optional)")

    output_dir = output_dir or (dataset_dir / "_upscaled")
    output_dir.mkdir(parents=True, exist_ok=True)

    images = img_utils.iter_images(dataset_dir)
    candidates = [p for p in images if img_utils.min_side(p) < upscale_target]

    if not candidates:
        rpt.ok(f"All images already ≥ {upscale_target}px — skipping upscale.")
        return {"upscaled": [], "rejected_post": [], "skipped": [str(p) for p in images]}

    rpt.info(f"{len(candidates)} images below {upscale_target}px min-side will be upscaled.")

    if upscaler is None:
        seedvr_available = bool(os.environ.get("SEEDVR_PATH", ""))
        if use_seedvr and seedvr_available:
            rpt.info("Using SeedVR upscaler (SEEDVR_PATH set).")
            upscaler = _seedvr_upscale
        else:
            if use_seedvr and not seedvr_available:
                rpt.warn("SEEDVR_PATH not set — falling back to Lanczos upscale.")
            upscaler = lambda p, o: _lanczos_upscale(p, o, upscale_target)

    results: dict = {"upscaled": [], "rejected_post": [], "skipped": []}

    for path in candidates:
        out_path = output_dir / path.name
        try:
            upscaler(path, out_path)
        except Exception as exc:
            rpt.error(f"Upscale failed for {path.name}: {exc}")
            results["skipped"].append(str(path))
            continue

        # Post-upscale hallucination check
        hall_ssim = _hallucination_check(path, out_path)
        if hall_ssim < HALLUCINATION_SSIM_THRESHOLD:
            rpt.warn(f"REJECT {path.name}: hallucinated texture post-upscale (SSIM={hall_ssim:.3f})")
            results["rejected_post"].append({"path": str(path), "hall_ssim": hall_ssim})
            out_path.unlink(missing_ok=True)
        else:
            rpt.ok(f"Upscaled {path.name} → {out_path.name} (hall_ssim={hall_ssim:.3f})")
            results["upscaled"].append({"original": str(path), "upscaled": str(out_path)})

    rpt.save_report(results, output_dir / "step3_report.json")
    return results
