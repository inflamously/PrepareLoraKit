"""Deterministic mock runtime for CurateStep (--mock)."""
from __future__ import annotations
from pathlib import Path

from prepare_lora_kit.cancellation import check_cancel
from prepare_lora_kit_pipeline.configs import CurateConfig

from .mock_embeddings import _mock_embeddings


def _mock_curate(
        working_dir: Path,
        output_dir: Path,
        cfg: CurateConfig,
        *,
        coverage_mode: str = "auto",
        enabled_substeps: list[str] | None = None,
        cancel_check=None,
) -> dict:
    from ..steps.s2_curate.coverage import _save_pca, _save_umap
    from ..steps.s2_curate.dedupe import _compute_hashes, _find_duplicates
    from ..utils import image as img_utils
    from ..utils import report as rpt

    rpt.step_header(2, "Curation — Mock Runtime")
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "CurateStep_report.json"

    images = img_utils.iter_images(working_dir)
    if not images:
        rpt.warn(f"No images in {working_dir}")
        return {}

    check_cancel(cancel_check)
    enabled = set(enabled_substeps or ["s2_1_dupecheck", "s2_2_clipscan", "s2_3_drop_images"])
    pairs = []
    if "s2_1_dupecheck" in enabled:
        hashes = _compute_hashes(images, cancel_check=cancel_check)
        pairs = _find_duplicates(hashes, cancel_check=cancel_check)
    to_drop: set[Path] = set()
    kept_images = list(images)
    check_cancel(cancel_check)

    coverage_path: Path | None = None
    coverage_metadata: dict | None = None
    mode = coverage_mode.lower().strip()
    if mode not in {"auto", "pca", "umap"}:
        mode = "auto"

    if "s2_2_clipscan" in enabled and len(kept_images) >= 2:
        check_cancel(cancel_check)
        embeddings = _mock_embeddings(kept_images)
        use_umap = mode == "umap" or (
                mode == "auto" and len(kept_images) > cfg.pca_umap_switch_threshold
        )
        if use_umap:
            coverage_path = reports_dir / "coverage_umap.png"
            coverage_metadata = _save_umap(embeddings, kept_images, coverage_path)
        else:
            coverage_path = reports_dir / "coverage_pca.png"
            coverage_metadata = _save_pca(embeddings, kept_images, coverage_path)

    report = {
        "mock_runtime": True,
        "duplicate_pairs": [(str(a), str(b), d) for a, b, d in pairs],
        "dropped_duplicates": [str(p) for p in to_drop],
        "kept_images": [str(p) for p in kept_images],
        "coverage_image": str(coverage_path) if coverage_path else None,
        "coverage": coverage_metadata,
        "substeps": {substep_id: {"enabled": substep_id in enabled} for substep_id in [
            "s2_1_dupecheck",
            "s2_2_clipscan",
            "s2_3_drop_images",
        ]},
    }
    rpt.info(f"Mock runtime: curated {len(kept_images)} image(s).")
    check_cancel(cancel_check)
    rpt.save_report(report, report_path)
    return report
