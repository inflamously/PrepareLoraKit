"""Copy finalized image + caption pairs into the export target folder.

Only ``added``/``modified`` entries are copied, preserving subject subfolders.
``orphaned`` target files are never touched (non-destructive export).
"""
from __future__ import annotations

import os
import shutil
from collections.abc import Iterable
from pathlib import Path


from prepare_lora_kit.cancellation import CancelCheck, check_cancel
from prepare_lora_kit.steps.export_step.diff import CAPTION_SUFFIX, DiffEntry

def export_entries(
    entries: Iterable[DiffEntry],
    target_dir: Path,
    *,
    excluded: Iterable[str] | None = None,
    cancel_check: CancelCheck | None = None,
) -> list[dict]:
    """Copy each non-excluded entry's image (+ caption) into ``target_dir``.

    Returns a list of ``{"rel", "image", "caption"?}`` records for the report.
    """
    target_dir = Path(target_dir)
    excluded_set = {str(rel) for rel in (excluded or ())}
    copied: list[dict] = []

    for entry in entries:
        if entry.rel in excluded_set:
            continue
        check_cancel(cancel_check)
        dst_image = target_dir / entry.rel
        os.makedirs(dst_image.parent, exist_ok=True)
        shutil.copy2(entry.image_src, dst_image)
        record = {"rel": entry.rel, "image": str(dst_image)}
        if entry.caption_src:
            dst_caption = dst_image.with_suffix(CAPTION_SUFFIX)
            shutil.copy2(entry.caption_src, dst_caption)
            record["caption"] = str(dst_caption)
        copied.append(record)

    return copied
