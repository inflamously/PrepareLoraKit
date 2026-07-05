"""Invoke adapter for VaeGateStep."""
from __future__ import annotations
from pathlib import Path

from prepare_lora_kit_pipeline.configs import VaeGateConfig

from .working_dataset import _require_working_dataset


def _invoke_VaeGateStep(working_dir: Path, output_dir: Path, cfg: VaeGateConfig,
                        *, network, **_kw) -> None:
    _require_working_dataset(working_dir)
    if _kw.get("mock_runtime"):
        from .mock_vae_gate import _mock_vae_gate
        _mock_vae_gate(
            working_dir,
            output_dir,
            interaction=_kw.get("interaction"),
            enabled_substeps=_kw.get("enabled_substeps"),
            cancel_check=_kw.get("cancel_check"),
        )
        return

    from ..steps import s4_vae_gate
    s4_vae_gate.run(
        working_dir,
        network=network,
        output_dir=working_dir,
        outlier_sigma=cfg.outlier_sigma,
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
