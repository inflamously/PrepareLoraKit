"""Invoke adapter for CurateStep."""
from __future__ import annotations
from pathlib import Path

from prepare_lora_kit_pipeline.configs import CurateConfig

from .working_dataset import _require_working_dataset


def _invoke_CurateStep(working_dir: Path, output_dir: Path, cfg: CurateConfig,
                       **_kw) -> None:
    _require_working_dataset(working_dir)
    if _kw.get("mock_runtime"):
        from .mock_curate import _mock_curate
        return _mock_curate(
            working_dir,
            output_dir,
            cfg,
            coverage_mode=str(_kw.get("mock_curate_coverage") or "auto"),
            enabled_substeps=_kw.get("enabled_substeps"),
            cancel_check=_kw.get("cancel_check"),
        )

    from ..steps import curate
    return curate.run(
        working_dir,
        output_dir=working_dir,
        auto_dedupe=True,
        skip_clip=cfg.skip_clip,
        report_path=output_dir / "reports" / "CurateStep_report.json",
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
        coverage_embedding_model=cfg.coverage_embedding_model,
        dedup_hamming_distance=cfg.dedup_hamming_distance,
        pca_umap_switch_threshold=cfg.pca_umap_switch_threshold,
    )
