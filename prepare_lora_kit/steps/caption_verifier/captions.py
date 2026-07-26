"""Caption discovery and write-back for CaptionVerifierStep.

Captions live as plain UTF-8 ``<stem>.txt`` sidecars beside their image inside
the working dataset (written by ``caption_bbox/workflow._write_caption``). This
module is the only place the verifier writes into that dataset, so it carries
the containment and atomicity rules.

No ML imports — this is pure filesystem work.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from prepare_lora_kit.steps.caption_bbox.artifacts import _is_bbox_artifact
from prepare_lora_kit.utils import image as img_utils

CAPTION_SUFFIX = ".txt"
_TMP_SUFFIX = ".plk_tmp"


def collect_verifiable_images(
    dataset_dir: Path, max_images: int | None = None,
) -> list[dict]:
    """Images in the working dataset that already have a caption sidecar.

    Generated ``plk_bbox__*`` region crops are excluded: they are real images
    with real ``.txt`` sidecars, but their captions are normalized artifacts
    keyed to ``plk_bbox__<stem>__boxes.json`` and must not be hand-edited here.
    """
    dataset_dir = Path(dataset_dir)
    found: list[dict] = []
    for path in img_utils.iter_images(dataset_dir):
        if _is_bbox_artifact(path):
            continue
        sidecar = path.with_suffix(CAPTION_SUFFIX)
        if not sidecar.is_file():
            continue
        found.append({
            "path": path,
            "name": path.name,
            "caption": _read_text(sidecar),
            "caption_path": sidecar,
        })
        if max_images and len(found) >= max_images:
            break
    return found


def write_caption_atomic(txt_path: Path, text: str) -> None:
    """Write a caption sidecar atomically.

    The write happens after a long interactive session; a cancel or crash
    mid-write would truncate a caption in the working dataset that AuditStep,
    BucketPoolsCheckStep and ExportStep all depend on. ``os.replace`` within the
    same directory is atomic on Windows too, which matters here.

    The temp name carries a ``.plk_tmp`` suffix so that both
    ``audit/checks.collect_stems`` (which matches ``.txt``) and
    ``utils.image.iter_images`` ignore it even if one ever leaks.
    """
    txt_path = Path(txt_path)
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = txt_path.with_name(f".{txt_path.name}{_TMP_SUFFIX}")
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, txt_path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def apply_caption_edits(
    dataset_dir: Path,
    edits: dict[str, str],
    *,
    backup_dir: Path | None = None,
) -> tuple[list[dict], list[dict]]:
    """Write edited captions back, returning ``(applied, rejected)``.

    Each entry is ``{path, before, after}``; rejected entries add ``reason``.

    The edited text is stored as typed apart from ``.strip()``. It is
    deliberately **not** re-normalized and the concept token is **not**
    re-injected: the entire point of a "wrong" verdict is that the user is
    removing a term the encoder mis-binds, and auto-restoring it would defeat
    the feature.
    """
    dataset_dir = Path(dataset_dir)
    root = dataset_dir.resolve()
    applied: list[dict] = []
    rejected: list[dict] = []

    for raw_path, raw_text in (edits or {}).items():
        key = str(raw_path)
        try:
            resolved = Path(key).resolve()
        except OSError:
            rejected.append({"path": key, "reason": "unreadable path"})
            continue

        # Keys arrive over the pywebview bridge from JS — treat as untrusted.
        if not _is_within(resolved, root):
            rejected.append({"path": key, "reason": "outside dataset"})
            continue
        # Defensive re-filter so a frontend bug cannot reach region sidecars.
        if _is_bbox_artifact(resolved):
            rejected.append({"path": key, "reason": "bbox region artifact"})
            continue
        if not resolved.is_file():
            rejected.append({"path": key, "reason": "missing image"})
            continue

        after = str(raw_text or "").strip()
        if not after:
            # An empty .txt makes AuditStep flag the image while ExportStep
            # still exports it — worse than leaving the original in place.
            rejected.append({"path": key, "reason": "empty caption"})
            continue

        sidecar = resolved.with_suffix(CAPTION_SUFFIX)
        before = _read_text(sidecar)
        if before == after:
            continue

        if backup_dir is not None:
            _backup(sidecar, resolved, root, Path(backup_dir))
        write_caption_atomic(sidecar, after)
        applied.append({"path": key, "before": before, "after": after})

    return applied, rejected


# --- internals -------------------------------------------------------------

def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return ""


def _is_within(candidate: Path, root: Path) -> bool:
    try:
        return candidate.is_relative_to(root)
    except AttributeError:  # pragma: no cover - Python < 3.9
        return str(candidate).startswith(str(root))


def _backup(sidecar: Path, image: Path, root: Path, backup_dir: Path) -> None:
    """Copy the original caption once, mirroring the dataset's subdirectories.

    Text files are free, and this is the only step that lets a human free-type
    directly into training data.
    """
    if not sidecar.is_file():
        return
    try:
        relative = image.relative_to(root).with_suffix(CAPTION_SUFFIX)
    except ValueError:  # pragma: no cover - guarded by _is_within
        relative = Path(sidecar.name)
    target = backup_dir / relative
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sidecar, target)
