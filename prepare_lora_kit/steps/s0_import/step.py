"""Step 0 - Import source images into the working dataset."""
from __future__ import annotations

import shutil
from pathlib import Path

from ...cancellation import CancelCheck, CancelledRun, check_cancel
from ...utils import report as rpt

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}


def run(
    input_dir: Path,
    output_dir: Path,
    report_path: Path | None = None,
    enabled_substeps: list[str] | None = None,
    cancel_check: CancelCheck | None = None,
) -> dict:
    """Copy source images into the working dataset directory."""

    rpt.step_header(0, "Import Source Images")
    images = _iter_images(input_dir)
    if not images:
        rpt.warn(f"No images found in {input_dir}")

    try:
        check_cancel(cancel_check)
        output_dir.mkdir(parents=True, exist_ok=True)
        imported: list[str] = []
        for path in images:
            check_cancel(cancel_check)
            dst = output_dir / path.name
            shutil.copy2(path, dst)
            imported.append(str(dst))
        check_cancel(cancel_check)
    except CancelledRun:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise

    report = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "imported": imported,
        "count": len(imported),
        "substeps": {
            "s0_import": {"enabled": "s0_import" in set(enabled_substeps or ["s0_import"])},
        },
    }
    rpt.info(f"Imported {len(imported)} image(s) into {output_dir}.")
    check_cancel(cancel_check)
    rpt.save_report(report, report_path or (output_dir / "ImportStep_report.json"))
    return report


def _iter_images(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS
    )
