"""
Step 6 — Pairing & Integrity Audit: check helpers.

Pure helper functions extracted from step.run(). Each keeps its report.* logging
calls so behavior and log messages remain identical to the inline version.
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image

from prepare_lora_kit.utils import image as img_utils
from prepare_lora_kit.report import reporter

_IMG_EXTS = img_utils.IMAGE_EXTS
_MIN_CAPTION = 5
_MAX_CAPTION = 600


def collect_stems(dataset_dir: Path) -> tuple[dict, dict]:
    image_stems: dict[str, Path] = {}
    txt_stems: dict[str, Path] = {}

    # Recurse so mirrored subdirectories are audited, and key by the relative
    # stem (subpath without extension) so an image pairs with the .txt beside it
    # and same-named files in different subdirs never collide.
    for p in sorted(dataset_dir.rglob("*")):
        if not p.is_file():
            continue
        rel_stem = str(p.relative_to(dataset_dir).with_suffix(""))
        if p.suffix.lower() in _IMG_EXTS:
            image_stems[rel_stem] = p
        elif p.suffix.lower() == ".txt":
            txt_stems[rel_stem] = p

    return image_stems, txt_stems


def check_pairing(image_stems, txt_stems) -> tuple[list, list, set]:
    orphan_images = [str(image_stems[s]) for s in image_stems if s not in txt_stems]
    orphan_txts = [str(txt_stems[s]) for s in txt_stems if s not in image_stems]

    if orphan_images:
        reporter.warn(f"{len(orphan_images)} orphan image(s) (no .txt):")
        for o in orphan_images:
            reporter.warn(f"  {Path(o).name}")
    if orphan_txts:
        reporter.warn(f"{len(orphan_txts)} orphan .txt(s) (no image):")
        for o in orphan_txts:
            reporter.warn(f"  {Path(o).name}")

    paired_stems = set(image_stems) & set(txt_stems)
    reporter.info(f"Paired pairs: {len(paired_stems)}")

    return orphan_images, orphan_txts, paired_stems


def check_corrupt(paired_stems, image_stems) -> list:
    corrupt: list[str] = []
    for stem in paired_stems:
        path = image_stems[stem]
        try:
            with Image.open(path) as img:
                img.verify()
        except Exception as exc:
            reporter.error(f"CORRUPT {path.name}: {exc}")
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
            reporter.error(f"EMPTY caption: {txt_path.name}")
        elif len(content) < _MIN_CAPTION:
            short_captions.append(str(txt_path))
            reporter.warn(f"SHORT caption ({len(content)} chars): {txt_path.name}")
        elif len(content) > _MAX_CAPTION:
            long_captions.append(str(txt_path))
            reporter.warn(f"LONG caption ({len(content)} chars): {txt_path.name}")

    return empty_captions, short_captions, long_captions


def check_resolution(paired_stems, image_stems, corrupt, min_resolution_side: int | None) -> list:
    undersized: list[dict] = []
    if min_resolution_side:
        reporter.info(f"Checking min_side against training resolution side: {min_resolution_side}px")
        for stem in paired_stems:
            p = image_stems[stem]
            if str(p) not in [c for c in corrupt]:
                try:
                    ms = img_utils.min_side(p)
                    if ms < min_resolution_side:
                        undersized.append({"path": str(p), "min_side": ms, "required": min_resolution_side})
                        reporter.warn(f"UNDERSIZED {p.name}: min_side={ms}px < {min_resolution_side}px")
                except Exception:
                    pass
    else:
        reporter.info("No minimum resolution configured — skipping resolution gate.")
    return undersized
