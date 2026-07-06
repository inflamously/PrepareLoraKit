"""Invoke adapter for UpscaleStep."""
from __future__ import annotations
from pathlib import Path

from prepare_lora_kit_pipeline.configs import UpscaleConfig

from .working_dataset import _require_working_dataset


def invoke_upscale_step(working_dir: Path, output_dir: Path, cfg: UpscaleConfig,
                        **_kw) -> None:
    _require_working_dataset(working_dir)
    from ..steps import upscale
    upscale.run(
        working_dir,
        output_dir=working_dir,
        upscale_target=cfg.upscale_target,
        upscale_highlight_threshold=cfg.upscale_highlight_threshold,
        upscale_model=cfg.upscale_model,
        hallucination_ssim_threshold=cfg.hallucination_ssim_threshold,
        report_path=output_dir / "reports" / "UpscaleStep_report.json",
        seedvr2_submodule_dir=cfg.seedvr2_submodule_dir,
        seedvr2_model_dir=cfg.seedvr2_model_dir,
        seedvr2_dit_model=cfg.seedvr2_dit_model,
        seedvr2_cuda_device=cfg.seedvr2_cuda_device,
        seedvr2_batch_size=cfg.seedvr2_batch_size,
        seedvr2_vae_tiled=cfg.seedvr2_vae_tiled,
        seedvr2_cache_models=cfg.seedvr2_cache_models,
        seedvr2_model_residency=cfg.seedvr2_model_residency,
        seedvr2_debug=cfg.seedvr2_debug,
        interaction=_kw.get("interaction"),
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
    )
