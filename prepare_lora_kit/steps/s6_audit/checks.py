"""
Step 6 — Pairing & Integrity Audit: check helpers.

Pure helper functions extracted from step.run(). Each keeps its rpt.* logging
calls so behavior and log messages remain identical to the inline version.
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image

from ...networks.base import NetworkProfile
from ...utils import image as img_utils
from ...utils import report as rpt

_IMG_EXTS = img_utils.IMAGE_EXTS
_MIN_CAPTION = 5
_MAX_CAPTION = 600


def collect_stems(dataset_dir: Path) -> tuple[dict, dict]:
    image_stems: dict[str, Path] = {}
    txt_stems: dict[str, Path] = {}

    for p in sorted(dataset_dir.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() in _IMG_EXTS:
            image_stems[p.stem] = p
        elif p.suffix.lower() == ".txt":
            txt_stems[p.stem] = p

    return image_stems, txt_stems


def check_pairing(image_stems, txt_stems) -> tuple[list, list, set]:
    orphan_images = [str(image_stems[s]) for s in image_stems if s not in txt_stems]
    orphan_txts = [str(txt_stems[s]) for s in txt_stems if s not in image_stems]

    if orphan_images:
        rpt.warn(f"{len(orphan_images)} orphan image(s) (no .txt):")
        for o in orphan_images:
            rpt.warn(f"  {Path(o).name}")
    if orphan_txts:
        rpt.warn(f"{len(orphan_txts)} orphan .txt(s) (no image):")
        for o in orphan_txts:
            rpt.warn(f"  {Path(o).name}")

    paired_stems = set(image_stems) & set(txt_stems)
    rpt.info(f"Paired pairs: {len(paired_stems)}")

    return orphan_images, orphan_txts, paired_stems


def check_corrupt(paired_stems, image_stems) -> list:
    corrupt: list[str] = []
    for stem in paired_stems:
        path = image_stems[stem]
        try:
            with Image.open(path) as img:
                img.verify()
        except Exception as exc:
            rpt.error(f"CORRUPT {path.name}: {exc}")
            corrupt.append(str(path))
    return corrupt


def check_captions(paired_stems, txt_stems) -> tuple[list, list, list]:
    empty_captions: list[str] = []
    short_captions: list[str] = []
    long_captions: list[str] = []

    for stem in paired_stems:
        txt_path = txt_stems[stem]
        content = txt_path.read_text(encoding="utf-8", errors="replace").strip()
        if not content:
            empty_captions.append(str(txt_path))
            rpt.error(f"EMPTY caption: {txt_path.name}")
        elif len(content) < _MIN_CAPTION:
            short_captions.append(str(txt_path))
            rpt.warn(f"SHORT caption ({len(content)} chars): {txt_path.name}")
        elif len(content) > _MAX_CAPTION:
            long_captions.append(str(txt_path))
            rpt.warn(f"LONG caption ({len(content)} chars): {txt_path.name}")

    return empty_captions, short_captions, long_captions


def check_resolution(paired_stems, image_stems, corrupt, network) -> list:
    undersized: list[dict] = []
    if network:
        max_side = network.max_bucket_side
        rpt.info(f"Checking min_side against largest bucket side: {max_side}px")
        for stem in paired_stems:
            p = image_stems[stem]
            if str(p) not in [c for c in corrupt]:
                try:
                    ms = img_utils.min_side(p)
                    if ms < max_side:
                        undersized.append({"path": str(p), "min_side": ms, "required": max_side})
                        rpt.warn(f"UNDERSIZED {p.name}: min_side={ms}px < {max_side}px")
                except Exception:
                    pass
    else:
        rpt.info("No network profile provided — skipping resolution gate.")
    return undersized
