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

from ...cancellation import CancelCheck, check_cancel
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
    enabled_substeps: list[str] | None = None,
    cancel_check: CancelCheck | None = None,
) -> dict:
    rpt.step_header(6, "Pairing & Integrity Audit")
    enabled = set(enabled_substeps or [
        "s6_1_pairing",
        "s6_2_corrupt",
        "s6_3_caption_quality",
        "s6_4_resolution",
    ])

    check_cancel(cancel_check)
    image_stems, txt_stems = collect_stems(dataset_dir)

    # ── 1. Pairing check ──────────────────────────────────────────────────────
    check_cancel(cancel_check)
    if "s6_1_pairing" in enabled:
        orphan_images, orphan_txts, paired_stems = check_pairing(image_stems, txt_stems)
    else:
        orphan_images, orphan_txts = [], []
        paired_stems = sorted(set(image_stems) & set(txt_stems))

    # ── 2. PIL verify (corrupt / truncated) ──────────────────────────────────
    check_cancel(cancel_check)
    corrupt = check_corrupt(paired_stems, image_stems) if "s6_2_corrupt" in enabled else []

    # ── 3. Caption quality ────────────────────────────────────────────────────
    check_cancel(cancel_check)
    if "s6_3_caption_quality" in enabled:
        empty_captions, short_captions, long_captions = check_captions(paired_stems, txt_stems)
    else:
        empty_captions, short_captions, long_captions = [], [], []

    # ── 4. Resolution gate ────────────────────────────────────────────────────
    check_cancel(cancel_check)
    undersized = (
        check_resolution(paired_stems, image_stems, corrupt, network)
        if "s6_4_resolution" in enabled
        else []
    )

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
        "substeps": {
            "s6_1_pairing": {"enabled": "s6_1_pairing" in enabled},
            "s6_2_corrupt": {"enabled": "s6_2_corrupt" in enabled},
            "s6_3_caption_quality": {"enabled": "s6_3_caption_quality" in enabled},
            "s6_4_resolution": {"enabled": "s6_4_resolution" in enabled},
        },
    }
    check_cancel(cancel_check)
    rpt.save_report(report, report_path or (dataset_dir / "step6_report.json"))
    return report
