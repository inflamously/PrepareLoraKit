"""
Step 2 — Curation

1. Perceptual-hash dedupe (phash, Hamming ≤ 8).
2. CLIP coverage: UMAP scatter (N > 30) or PCA scatter (N ≤ 30).
3. Occlusion filter via CLIP zero-shot.
"""
from __future__ import annotations
from pathlib import Path

from ...utils import image as img_utils
from ...utils import report as rpt

from .dedupe import _compute_hashes, _find_duplicates, _resolve_duplicates
from .coverage import _clip_embeddings, _save_umap, _save_pca
from .occlusion import OCCLUSION_THRESHOLD, _occlusion_scores


def run(
    dataset_dir: Path,
    output_dir: Path | None = None,
    auto_dedupe: bool = True,
    skip_clip: bool = False,
    report_path: Path | None = None,
) -> dict:
    rpt.step_header(2, "Curation — Dedupe + Coverage")

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

    rpt.info(f"Found {len(images)} images. Computing perceptual hashes …")
    hashes = _compute_hashes(images)

    pairs = _find_duplicates(hashes)
    rpt.info(f"Near-duplicate pairs: {len(pairs)}")
    to_drop = _resolve_duplicates(pairs, auto_drop=auto_dedupe) if pairs else set()

    kept_images = [p for p in images if p not in to_drop]
    rpt.ok(f"After dedupe: {len(kept_images)} images ({len(to_drop)} dropped)")

    # Coverage
    coverage_path: Path | None = None
    if not skip_clip:
        try:
            emb = _clip_embeddings(kept_images)
            if len(kept_images) > 30:
                rpt.info("Computing CLIP embeddings for UMAP coverage …")
                coverage_path = artifact_dir / "coverage_umap.png"
                _save_umap(emb, kept_images, coverage_path)
            else:
                rpt.info("Computing CLIP embeddings for PCA coverage …")
                coverage_path = artifact_dir / "coverage_pca.png"
                _save_pca(emb, kept_images, coverage_path)
        except Exception as exc:
            rpt.warn(f"Coverage visualisation failed: {exc}")

    # Occlusion filter
    occluded: list[str] = []
    if not skip_clip:
        try:
            rpt.info("Running occlusion filter (CLIP zero-shot) …")
            occ_scores = _occlusion_scores(kept_images)
            occluded = [str(p) for p, s in occ_scores.items() if s < OCCLUSION_THRESHOLD]
            if occluded:
                rpt.warn(f"{len(occluded)} images flagged as possibly occluded/ambiguous:")
                for o in occluded:
                    rpt.warn(f"  {Path(o).name}")
        except Exception as exc:
            rpt.warn(f"Occlusion filter failed: {exc}")

    img_utils.materialize(kept_images, dataset_dir, output_dir)

    report = {
        "duplicate_pairs": [(str(a), str(b), d) for a, b, d in pairs],
        "dropped_duplicates": [str(p) for p in to_drop],
        "kept_images": [str(p) for p in kept_images],
        "occluded_flagged": occluded,
        "coverage_image": str(coverage_path) if coverage_path else None,
    }
    rpt.save_report(report, report_path)
    return report
