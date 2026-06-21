from __future__ import annotations
import os
import subprocess
from pathlib import Path

UPSCALE_TARGET = 3072


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
