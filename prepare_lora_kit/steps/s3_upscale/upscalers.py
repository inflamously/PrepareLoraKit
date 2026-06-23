from __future__ import annotations
from pathlib import Path

UPSCALE_TARGET = 3072


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
