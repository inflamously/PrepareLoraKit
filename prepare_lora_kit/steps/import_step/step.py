"""Step 0 - Import source images into the working dataset."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from prepare_lora_kit.cancellation import CancelCheck, CancelledRun, check_cancel
from prepare_lora_kit.utils.report import save_report, info, step_header, warn

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}


def get_recursive_mirror_paths(root_path: Path, item_path: Path) -> Path:
    return item_path.relative_to(root_path)


def run(
        input_dir: Path,
        output_dir: Path,
        report_path: Path | None = None,
        enabled_substeps: list[str] | None = None,
        cancel_check: CancelCheck | None = None,
) -> dict:
    """Copy source images into the working dataset directory."""

    step_header(0, "Import Source Images")
    image_paths = _iter_images(input_dir)
    if not image_paths:
        warn(f"No images found in {input_dir}")

    try:
        check_cancel(cancel_check)
        output_dir.mkdir(parents=True, exist_ok=True)
        imported: list[str] = []
        for i in range(len(image_paths)):
            source_image_path = image_paths[i]
            target_image_path = get_recursive_mirror_paths(input_dir, source_image_path)
            check_cancel(cancel_check)
            dst = output_dir / target_image_path
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(source_image_path, dst)
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
            "import_images": {"enabled": "import_images" in set(enabled_substeps or ["import_images"])},
        },
    }
    info(f"Imported {len(imported)} image(s) into {output_dir}.")
    check_cancel(cancel_check)
    save_report(report, report_path or (output_dir / "ImportStep_report.json"))
    return report


def _iter_images(folder: Path) -> list[Path]:
    images = []
    for root, dirs, files in os.walk(folder):
        for file in files:
            path = Path(root) / Path(file)
            if path.is_file() and path.suffix in IMAGE_EXTS:
                images.append(path)
    return images
