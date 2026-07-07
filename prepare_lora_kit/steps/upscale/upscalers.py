from __future__ import annotations
from pathlib import Path

UPSCALE_TARGET = 3072
UPSCALE_HIGHLIGHT_THRESHOLD = 1536


def _lanczos_upscale(path: Path, output_path: Path, target: int = UPSCALE_TARGET) -> Path:
    """Resize ``path`` up to ``target`` and save at ``output_path``.

    The caller (upscale/step.py) decides ``output_path``'s extension —
    JPEG sources get routed to a ``.png`` destination so PIL's format
    inference (by extension) writes PNG without any extra handling here.
    """
    from PIL import Image


    from prepare_lora_kit.steps.upscale.jpeg_cleanup import _denoise, _is_jpeg
    img = Image.open(path).convert("RGB")
    if _is_jpeg(path):
        # Lanczos has no learned restoration of its own, so denoise the
        # JPEG source before resizing instead of just rescaling its
        # compression artifacts along with the content.
        img = _denoise(img)
    w, h = img.size
    ms = min(w, h)
    scale = target / ms
    new_w, new_h = int(w * scale), int(h * scale)
    up = img.resize((new_w, new_h), Image.LANCZOS)
    up.save(output_path)
    return output_path
