"""Invoke adapter for VaeGateStep."""
from __future__ import annotations
from pathlib import Path


from prepare_lora_kit.pipeline.configs import VaeGateConfig

from prepare_lora_kit.invoke.working_dataset import _require_working_dataset

def invoke_vae_gate_step(working_dir: Path, output_dir: Path, cfg: VaeGateConfig,
                         **_kw) -> dict:
    _require_working_dataset(working_dir)
    if _kw.get("mock_runtime"):
        from prepare_lora_kit.invoke.mock_vae_gate import _mock_vae_gate
        return _mock_vae_gate(
            working_dir,
            output_dir,
            interaction=_kw.get("interaction"),
            enabled_substeps=_kw.get("enabled_substeps"),
            cancel_check=_kw.get("cancel_check"),
        )

    from prepare_lora_kit.steps import vae_gate
    return vae_gate.run(
        working_dir,
        vae_model_id=cfg.vae_model_id,
        vae_config_id=cfg.vae_config_id,
        output_dir=working_dir,
        outlier_sigma=cfg.outlier_sigma,
        hf_cutoff_fraction=cfg.hf_cutoff_fraction,
        seed=cfg.seed,
        report_path=output_dir / "reports" / "VaeGateStep_report.json",
        interaction=_kw.get("interaction"),
        diff_amplification=cfg.diff_amplification,
        gaussian_blur_sigma=cfg.gaussian_blur_sigma,
        gaussian_blur_kernel=cfg.gaussian_blur_kernel,
        otsu_enabled=cfg.otsu_enabled,
        output_previews=cfg.output_previews,
        output_silhouettes=cfg.output_silhouettes,
        output_hard_silhouettes=cfg.output_hard_silhouettes,
        max_side=cfg.max_side,
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
    )
