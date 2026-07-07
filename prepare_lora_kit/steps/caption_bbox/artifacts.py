"""Generated bbox training item helpers for Step 5."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


from prepare_lora_kit.utils import caption as cap_utils
BBOX_PREFIX = "plk_bbox__"

# Fields persisted per box in the reload sidecar. Coordinates are normalized
# (0–1); crop_name links back to the region crop saved by _save_bbox_training_item.
_BOX_COORD_KEYS = ("x1", "y1", "x2", "y2")


def _is_bbox_artifact(path: Path) -> bool:
    return path.stem.startswith(BBOX_PREFIX)


def _clean_bbox_artifacts(folder: Path) -> None:
    for path in folder.rglob("*"):
        if path.is_file() and path.stem.startswith(BBOX_PREFIX):
            path.unlink(missing_ok=True)


def _bbox_stem(source: Path, index: int) -> str:
    return f"{BBOX_PREFIX}{source.stem}__{index:02d}"


def _boxes_sidecar_path(source: Path) -> Path:
    """Where a source image's reloadable bbox coordinates are stored.

    Uses the ``plk_bbox__`` prefix so ``_is_bbox_artifact`` keeps it out of the
    caption source list. These reload sidecars are hand-drawn-box state and are
    deliberately preserved across re-runs (including --force); only an explicit
    ``_clean_bbox_artifacts`` call removes them.
    """
    return source.parent / f"{BBOX_PREFIX}{source.stem}__boxes.json"


def save_boxes_sidecar(source: Path, annotations: list[dict]) -> Path | None:
    """Persist a source image's bbox coords + labels so they can be reloaded.

    Only normalized coordinates, the label, and the linking ``crop_name`` are kept
    (crop_path/sidecar_path are re-derived on load). Submitting an empty list clears
    a previous sidecar so reload reflects "no boxes".
    """
    sidecar = _boxes_sidecar_path(source)
    records: list[dict] = []
    for ann in annotations:
        if not isinstance(ann, dict):
            continue
        try:
            record = {k: float(ann[k]) for k in _BOX_COORD_KEYS}
        except (KeyError, TypeError, ValueError):
            continue
        record["label"] = str(ann.get("label") or "")
        crop_name = ann.get("crop_name")
        if crop_name:
            record["crop_name"] = str(crop_name)
        records.append(record)

    if not records:
        sidecar.unlink(missing_ok=True)
        return None
    sidecar.write_text(json.dumps(records, indent=2), encoding="utf-8")
    return sidecar


def load_boxes_sidecar(source: Path) -> list[dict]:
    """Read previously-saved bbox coords for a source image (empty if absent/bad).

    Re-resolves each box's ``crop_path``/``sidecar_path`` from ``crop_name`` when
    those region artifacts still exist beside the source, so the UI can show the
    captioned region and edits round-trip to the right sidecar.
    """
    sidecar = _boxes_sidecar_path(source)
    if not sidecar.is_file():
        return []
    try:
        records = json.loads(sidecar.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    if not isinstance(records, list):
        return []

    boxes: list[dict] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        try:
            box = {k: float(record[k]) for k in _BOX_COORD_KEYS}
        except (KeyError, TypeError, ValueError):
            continue
        box["label"] = str(record.get("label") or "")
        crop_name = record.get("crop_name")
        if crop_name:
            box["crop_name"] = str(crop_name)
            crop_path = source.parent / str(crop_name)
            if crop_path.is_file():
                box["crop_path"] = str(crop_path)
                txt_path = crop_path.with_suffix(".txt")
                if txt_path.is_file():
                    box["sidecar_path"] = str(txt_path)
        boxes.append(box)
    return boxes


def _normalize_bbox_caption(caption: str, concept_token: str | None) -> str:
    """Clean a region caption and ensure the concept token leads it.

    Mirrors the initial-write normalization (strip boilerplate, capitalize, prepend
    the token). A concept token already at the front is preserved verbatim and split
    off first, so re-normalizing an already-tokened caption — e.g. an edited region
    label that displays as ``"tok, ..."`` — stays idempotent and never recapitalizes
    or duplicates the token.
    """
    text = caption.strip()
    prefix = ""
    if concept_token:
        token = concept_token.strip()
        for sep in (", ", ",", " "):
            candidate = f"{token}{sep}"
            if token and text.lower().startswith(candidate.lower()):
                prefix = f"{token}, "
                text = text[len(candidate):]
                break

    body = cap_utils.strip_boilerplate(text)
    if prefix:
        return f"{prefix}{body}"
    if concept_token and body and not cap_utils.token_present(body, concept_token):
        return f"{concept_token}, {body}"
    return body


def _update_bbox_caption(sidecar_path: Path, label: str, concept_token: str | None) -> str:
    """Rewrite an existing region sidecar from an edited label and return the text."""
    final_caption = _normalize_bbox_caption(label, concept_token)
    sidecar_path.write_text(final_caption, encoding="utf-8")
    return final_caption


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

    final_caption = _normalize_bbox_caption(caption, concept_token)

    crop.convert("RGB").save(img_path)
    txt_path.write_text(final_caption, encoding="utf-8")
    return {
        "caption": final_caption,
        "crop_path": str(img_path),
        "crop_name": img_path.name,
        "sidecar_path": str(txt_path),
    }
