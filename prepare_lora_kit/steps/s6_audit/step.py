"""
Step 6 — Pairing & Integrity Audit

Checks:
  1. Every image has exactly one .txt sidecar (no orphans either direction).
  2. PIL verify() — no truncated/corrupt files.
  3. No empty captions, no extreme caption-length outliers.
  4. No images with min_side < largest bucket resolution.
"""
from __future__ import annotations
from pathlib import Path

from ...networks.base import NetworkProfile
from ...utils import report as rpt

from .checks import (
    collect_stems,
    check_pairing,
    check_corrupt,
    check_captions,
    check_resolution,
)


def run(
    dataset_dir: Path,
    network: NetworkProfile | None = None,
    report_path: Path | None = None,
) -> dict:
    rpt.step_header(6, "Pairing & Integrity Audit")

    image_stems, txt_stems = collect_stems(dataset_dir)

    # ── 1. Pairing check ──────────────────────────────────────────────────────
    orphan_images, orphan_txts, paired_stems = check_pairing(image_stems, txt_stems)

    # ── 2. PIL verify (corrupt / truncated) ──────────────────────────────────
    corrupt = check_corrupt(paired_stems, image_stems)

    # ── 3. Caption quality ────────────────────────────────────────────────────
    empty_captions, short_captions, long_captions = check_captions(paired_stems, txt_stems)

    # ── 4. Resolution gate ────────────────────────────────────────────────────
    undersized = check_resolution(paired_stems, image_stems, corrupt, network)

    # ── Summary ───────────────────────────────────────────────────────────────
    issues = len(orphan_images) + len(orphan_txts) + len(corrupt) + len(empty_captions) + len(undersized)

    if issues == 0:
        rpt.ok(f"All {len(paired_stems)} pairs passed integrity audit.")
    else:
        rpt.warn(f"{issues} issue(s) found across {len(paired_stems)} pairs.")

    report = {
        "paired": len(paired_stems),
        "orphan_images": orphan_images,
        "orphan_txts": orphan_txts,
        "corrupt": corrupt,
        "empty_captions": empty_captions,
        "short_captions": short_captions,
        "long_captions": long_captions,
        "undersized": undersized,
        "pass": issues == 0,
    }
    rpt.save_report(report, report_path or (dataset_dir / "step6_report.json"))
    return report
