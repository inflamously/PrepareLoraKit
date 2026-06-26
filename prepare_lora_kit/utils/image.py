"""Low-level image quality metrics used by multiple steps."""
from __future__ import annotations
from pathlib import Path
import io
import shutil
import cv2
import numpy as np
from PIL import Image


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def iter_images(folder: Path) -> list[Path]:
    """Recursively collect images under ``folder`` (mirrored-subdir aware)."""
    return sorted(p for p in folder.rglob("*") if p.is_file() and is_image(p))


def _prune_empty_dirs(root: Path) -> None:
    """Remove empty subdirectories under ``root`` (never ``root`` itself)."""
    for d in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()


def materialize(survivors, src_dir: Path, output_dir: Path) -> None:
    """Make ``output_dir`` hold exactly the images in ``survivors``.

    Images may live in mirrored subdirectories under ``src_dir``; their relative
    subpaths are preserved either way.

    Two modes, picked by whether output_dir is the folder the images already
    live in:

    - **in-place** (output_dir == src_dir): the pipeline's single working dir.
      Delete every image NOT in survivors; survivors stay put — no copy, no
      per-step duplication. Empty subdirectories left behind are pruned.
    - **copy** (output_dir != src_dir): standalone single-step CLI use, where
      the caller points -i and -o at different folders. Copy survivors across,
      recreating their relative subpaths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    keep = {Path(s).resolve() for s in survivors}
    if output_dir.resolve() == src_dir.resolve():
        for p in iter_images(src_dir):
            if p.resolve() not in keep:
                p.unlink()
        _prune_empty_dirs(src_dir)
    else:
        for s in survivors:
            s = Path(s)
            dst = output_dir / s.relative_to(src_dir)
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(s, dst)


def load_cv2(path: Path) -> np.ndarray:
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"cv2 could not read {path}")
    return img


# ── Blur ──────────────────────────────────────────────────────────────────────

def blur_score(path: Path) -> float:
    """Laplacian variance — lower = blurrier. Typical threshold: 100."""
    gray = cv2.cvtColor(load_cv2(path), cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


# ── Noise ─────────────────────────────────────────────────────────────────────

def noise_score(path: Path) -> float:
    """Estimate noise level from the high-frequency residual."""
    gray = cv2.cvtColor(load_cv2(path), cv2.COLOR_BGR2GRAY).astype(np.float32)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    residual = gray - blurred
    return float(residual.std())


# ── JPEG artifacts ────────────────────────────────────────────────────────────

def jpeg_artifact_score(path: Path) -> float:
    """
    SSIM between the original and a re-compressed copy at Q=75.
    Returns 1.0 - SSIM so higher = worse artifacts.
    """
    from skimage.metrics import structural_similarity as ssim

    pil = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=75)
    buf.seek(0)
    compressed = Image.open(buf).convert("RGB")

    orig_arr = np.array(pil)
    comp_arr = np.array(compressed)
    score = ssim(orig_arr, comp_arr, channel_axis=2, data_range=255)
    return float(1.0 - score)


# ── Watermark (CLIP zero-shot) ─────────────────────────────────────────────────

_clip_model = None
_clip_processor = None


def _get_clip():
    global _clip_model, _clip_processor
    if _clip_model is None:
        from transformers import CLIPModel, CLIPProcessor
        _clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        _clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        _clip_model.eval()
    return _clip_model, _clip_processor


def watermark_score(path: Path) -> float:
    """
    CLIP zero-shot score for 'photo with visible watermark'.
    Returns probability in [0, 1]; higher = more likely watermarked.
    """
    import torch
    model, processor = _get_clip()
    image = Image.open(path).convert("RGB")
    prompts = ["a photo with a visible watermark or logo", "a clean photo without watermarks"]
    inputs = processor(text=prompts, images=image, return_tensors="pt", padding=True)
    with torch.no_grad():
        logits = model(**inputs).logits_per_image[0]
        probs = logits.softmax(dim=0)
    return float(probs[0].item())


# ── Size helpers ───────────────────────────────────────────────────────────────

def min_side(path: Path) -> int:
    with Image.open(path) as img:
        return min(img.size)


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as img:
        return img.size  # (width, height)


# ── SSIM utility ──────────────────────────────────────────────────────────────

def ssim_pair(a: np.ndarray, b: np.ndarray) -> float:
    from skimage.metrics import structural_similarity as ssim
    if a.ndim == 3:
        return float(ssim(a, b, channel_axis=2, data_range=255))
    return float(ssim(a, b, data_range=255))
