"""Low-level image quality metrics used by multiple steps."""
from __future__ import annotations
from pathlib import Path
import io
import shutil
import threading
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


# ── Decode-once cache ───────────────────────────────────────────────────────────
# A single image is fed to several scorers (blur/noise/jpeg/watermark/min_side);
# decoding it once and sharing the BGR / gray / PIL views avoids 4–5× redundant
# disk decode per image. The metric functions below accept either a Path (decode
# on demand, used by other steps) or an ImageData (reuse the cached decode).

class ImageData:
    """Lazily decodes an image once and caches its BGR / gray / PIL views."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._bgr: np.ndarray | None = None
        self._gray: np.ndarray | None = None
        self._pil: Image.Image | None = None

    @property
    def bgr(self) -> np.ndarray:
        if self._bgr is None:
            self._bgr = load_cv2(self.path)
        return self._bgr

    @property
    def gray(self) -> np.ndarray:
        if self._gray is None:
            self._gray = cv2.cvtColor(self.bgr, cv2.COLOR_BGR2GRAY)
        return self._gray

    @property
    def pil(self) -> Image.Image:
        if self._pil is None:
            self._pil = Image.open(self.path).convert("RGB")
        return self._pil


def _as_data(src) -> ImageData:
    return src if isinstance(src, ImageData) else ImageData(src)


# ── Blur ──────────────────────────────────────────────────────────────────────

def blur_score(src) -> float:
    """Laplacian variance — lower = blurrier. Typical threshold: 100."""
    gray = _as_data(src).gray
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


# ── Noise ─────────────────────────────────────────────────────────────────────

def noise_score(src) -> float:
    """Estimate noise level from the high-frequency residual."""
    gray = _as_data(src).gray.astype(np.float32)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    residual = gray - blurred
    return float(residual.std())


# ── JPEG artifacts ────────────────────────────────────────────────────────────

def jpeg_artifact_score(src) -> float:
    """
    SSIM between the original and a re-compressed copy at Q=75.
    Returns 1.0 - SSIM so higher = worse artifacts.
    """
    from skimage.metrics import structural_similarity as ssim

    pil = _as_data(src).pil
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
_clip_device = None
_clip_lock = threading.Lock()  # CLIP forward is not thread-safe; guard it.


def _get_clip():
    global _clip_model, _clip_processor, _clip_device
    # Double-checked locking: under the thread pool, several workers hit this at
    # once on the first image. transformers' lazy module loader is not safe to
    # initialise concurrently (a racing thread sees a half-built module and fails
    # with "cannot import name 'CLIPModel'"), so serialise the one-time load.
    if _clip_model is None:
        with _clip_lock:
            if _clip_model is None:
                import torch
                from transformers import CLIPModel, CLIPProcessor
                _clip_device = "cuda" if torch.cuda.is_available() else "cpu"
                model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval().to(_clip_device)
                _clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
                _clip_model = model  # publish last: other threads see a ready model
    return _clip_model, _clip_processor, _clip_device


def unload_watermark_model() -> None:
    """Release the cached watermark CLIP model and its CUDA allocations."""
    global _clip_model, _clip_processor, _clip_device

    with _clip_lock:
        used_cuda = _clip_device == "cuda"
        _clip_model = None
        _clip_processor = None
        _clip_device = None

    if used_cuda:
        import torch

        torch.cuda.empty_cache()


def watermark_score(src) -> float:
    """
    CLIP zero-shot score for 'photo with visible watermark'.
    Returns probability in [0, 1]; higher = more likely watermarked.
    """
    import torch
    model, processor, device = _get_clip()
    image = _as_data(src).pil
    prompts = ["a photo with a visible watermark or logo", "a clean photo without watermarks"]
    inputs = processor(text=prompts, images=image, return_tensors="pt", padding=True).to(device)
    with _clip_lock, torch.no_grad():
        logits = model(**inputs).logits_per_image[0]
        probs = logits.softmax(dim=0)
    return float(probs[0].item())


# ── Size helpers ───────────────────────────────────────────────────────────────

def min_side(src) -> int:
    # ImageData → reuse the already-decoded array; Path → cheap header-only read
    # (upscale/audit callers pass Path purely for dimensions, must not force a decode).
    if isinstance(src, ImageData):
        h, w = src.bgr.shape[:2]
        return int(min(h, w))
    with Image.open(src) as img:
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
