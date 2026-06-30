"""
Step 2 — Curation

1. Perceptual-hash dedupe (phash, configurable Hamming distance).
2. Coverage embedding (CLIP/DINOv2/Qwen, VRAM-auto): UMAP (N > 30) or PCA (N ≤ 30) scatter.
"""
from __future__ import annotations
from pathlib import Path

from ...cancellation import CancelCheck, CancelledRun, check_cancel
from ...utils import image as img_utils
from ...utils import report as rpt

from .dedupe import _compute_hashes, _find_duplicates, _resolve_duplicates
from .coverage import _coverage_embeddings, _save_umap, _save_pca


def _resolve_coverage_model(coverage_embedding_model: str | None) -> str:
    """Resolve the coverage model, expanding ``auto`` from detected VRAM."""
    from ...embedding import catalog, vram

    choice = (coverage_embedding_model or catalog.AUTO).strip()
    if choice == catalog.AUTO:
        return catalog.auto_select(vram.total_vram_gb())
    return catalog.normalize_id(choice)


def run(
    dataset_dir: Path,
    output_dir: Path | None = None,
    auto_dedupe: bool = True,
    skip_clip: bool = False,
    report_path: Path | None = None,
    enabled_substeps: list[str] | None = None,
    cancel_check: CancelCheck | None = None,
    coverage_embedding_model: str | None = None,
    dedup_hamming_distance: int = 3,
    pca_umap_switch_threshold: int = 30,
) -> dict:
    rpt.step_header(2, "Curation — Dedupe + Coverage")
    enabled = set(enabled_substeps or ["s2_1_dupecheck", "s2_2_clipscan", "s2_3_drop_images"])

    output_dir = output_dir or dataset_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    # Reports + coverage plot land beside the report (the flat run dir under the
    # pipeline), never inside the working image dir.
    report_path = report_path or (output_dir / "step2_report.json")
    artifact_dir = report_path.parent
    artifact_dir.mkdir(parents=True, exist_ok=True)

    images = img_utils.iter_images(dataset_dir)
    if not images:
        rpt.warn(f"No images in {dataset_dir}")
        return {}

    pairs = []
    to_drop: set[Path] = set()
    if "s2_1_dupecheck" in enabled:
        rpt.info(f"Found {len(images)} images. Computing perceptual hashes …")
        hashes = _compute_hashes(images, cancel_check=cancel_check)

        pairs = _find_duplicates(
            hashes, max_distance=dedup_hamming_distance, cancel_check=cancel_check
        )
        rpt.info(f"Near-duplicate pairs: {len(pairs)}")
        to_drop = _resolve_duplicates(
            pairs,
            auto_drop=auto_dedupe,
            cancel_check=cancel_check,
        ) if pairs else set()
    else:
        rpt.warn("Skipping duplicate check substep.")

    apply_drops = "s2_3_drop_images" in enabled
    kept_images = [p for p in images if apply_drops and p not in to_drop or not apply_drops]
    if apply_drops:
        rpt.ok(f"After dedupe: {len(kept_images)} images ({len(to_drop)} dropped)")
    else:
        rpt.info(f"Drop-images substep disabled; retaining all {len(images)} image(s).")

    # Resolve embedding model selection once for the clipscan substep.
    coverage_model = _resolve_coverage_model(coverage_embedding_model)

    # Coverage
    coverage_path: Path | None = None
    coverage_metadata: dict | None = None
    if not skip_clip and "s2_2_clipscan" in enabled:
        try:
            rpt.info(f"Computing coverage embeddings ({coverage_model}) …")
            emb = _coverage_embeddings(kept_images, coverage_model, cancel_check=cancel_check)
            if len(kept_images) > pca_umap_switch_threshold:
                coverage_path = artifact_dir / "coverage_umap.png"
                coverage_metadata = _save_umap(emb, kept_images, coverage_path, coverage_model)
            else:
                coverage_path = artifact_dir / "coverage_pca.png"
                coverage_metadata = _save_pca(emb, kept_images, coverage_path, coverage_model)
        except CancelledRun:
            raise
        except Exception as exc:
            coverage_path = None
            coverage_metadata = None
            rpt.warn(f"Coverage visualisation failed: {exc}")

    check_cancel(cancel_check)
    img_utils.materialize(kept_images, dataset_dir, output_dir)

    report = {
        "duplicate_pairs": [(str(a), str(b), d) for a, b, d in pairs],
        "dropped_duplicates": [str(p) for p in to_drop] if apply_drops else [],
        "duplicate_drop_candidates": [str(p) for p in to_drop],
        "kept_images": [str(p) for p in kept_images],
        "coverage_image": str(coverage_path) if coverage_path else None,
        "coverage": coverage_metadata,
        "substeps": {
            "s2_1_dupecheck": {"enabled": "s2_1_dupecheck" in enabled},
            "s2_2_clipscan": {"enabled": (not skip_clip) and "s2_2_clipscan" in enabled},
            "s2_3_drop_images": {"enabled": apply_drops},
        },
    }
    check_cancel(cancel_check)
    rpt.save_report(report, report_path)
    return report
