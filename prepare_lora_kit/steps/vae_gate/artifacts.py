"""Dataset materialization and preview cleanup for :mod:`vae_gate`."""
from __future__ import annotations

import shutil
from pathlib import Path

from prepare_lora_kit.utils import image as img_utils


def _materialize_with_captions(
    images: list[Path],
    survivors: list[Path],
    dataset_dir: Path,
    output_dir: Path,
) -> None:
    """Materialize selected images and keep matching caption sidecars paired."""
    survivor_paths = {path.resolve() for path in survivors}
    in_place = dataset_dir.resolve() == output_dir.resolve()
    img_utils.materialize(survivors, dataset_dir, output_dir)

    if in_place:
        for path in images:
            if path.resolve() not in survivor_paths:
                path.with_suffix(".txt").unlink(missing_ok=True)
        return

    for path in survivors:
        caption = path.with_suffix(".txt")
        if caption.is_file():
            destination = (output_dir / path.relative_to(dataset_dir)).with_suffix(".txt")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(caption, destination)


def _prune_unrequested_artifacts(
    artifacts: dict[str, dict],
    preview_root: Path,
    *,
    keep_vae: bool,
    keep_diff: bool,
    keep_hard: bool,
) -> None:
    """Remove UI-temporary views after review while preserving requested outputs."""
    keep_by_view = {"vae": keep_vae, "diff": keep_diff, "hard": keep_hard}
    resolved_root = preview_root.resolve()
    for artifact in artifacts.values():
        _drop_unkept_views(artifact.get("views", {}), keep_by_view, resolved_root)
    _remove_empty_dirs(preview_root)


def _drop_unkept_views(
    views: dict,
    keep_by_view: dict[str, bool],
    resolved_root: Path,
) -> None:
    """Delete and unregister unrequested views owned by the preview directory."""
    for view, keep in keep_by_view.items():
        if keep:
            continue
        raw_path = views.pop(view, None)
        if not raw_path:
            continue
        path = Path(raw_path)
        if path.resolve().is_relative_to(resolved_root):
            path.unlink(missing_ok=True)


def _remove_empty_dirs(preview_root: Path) -> None:
    """Prune directories left empty by pruning, deepest first, root included."""
    if not preview_root.exists():
        return
    for directory in sorted(
        (path for path in preview_root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        if not any(directory.iterdir()):
            directory.rmdir()
    if not any(preview_root.iterdir()):
        preview_root.rmdir()
