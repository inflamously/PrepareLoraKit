"""Generated bbox training item helpers for Step 5."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ...utils import caption as cap_utils

BBOX_PREFIX = "plk_bbox__"


def _is_bbox_artifact(path: Path) -> bool:
    return path.stem.startswith(BBOX_PREFIX)


def _clean_bbox_artifacts(folder: Path) -> None:
    for path in folder.rglob("*"):
        if path.is_file() and path.stem.startswith(BBOX_PREFIX):
            path.unlink(missing_ok=True)


def _bbox_stem(source: Path, index: int) -> str:
    return f"{BBOX_PREFIX}{source.stem}__{index:02d}"


def _save_bbox_training_item(
    crop: Any,
    source_path: Path,
    output_dir: Path,
    caption: str,
    concept_token: str | None,
) -> dict[str, str]:
    # Keep region crops in the same subdirectory as their source image so the
    # mirrored dataset layout is preserved (output_dir is the dataset root).
    artifact_dir = source_path.parent
    count = len(list(artifact_dir.glob(f"{BBOX_PREFIX}{source_path.stem}__*.png"))) + 1
    stem = _bbox_stem(source_path, count)
    img_path = artifact_dir / f"{stem}.png"
    txt_path = artifact_dir / f"{stem}.txt"

    final_caption = cap_utils.strip_boilerplate(caption)
    if concept_token and final_caption and not cap_utils.token_present(final_caption, concept_token):
        final_caption = f"{concept_token}, {final_caption}"

    crop.convert("RGB").save(img_path)
    txt_path.write_text(final_caption, encoding="utf-8")
    return {
        "caption": final_caption,
        "crop_path": str(img_path),
        "crop_name": img_path.name,
        "sidecar_path": str(txt_path),
    }
