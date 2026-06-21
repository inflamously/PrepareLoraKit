"""
Per-step invoke adapters — bridge a PipelineStep's config to its step module's
``run()`` entry point. ``STEP_INVOKE_MAP`` maps a step type to its adapter.

Each adapter signature: (working_dir, output_dir, cfg, *, network, concept_token, original_dir)
"""
from __future__ import annotations
import dataclasses
import shutil
from pathlib import Path
from typing import Callable, Optional

from .project.configs import (
    QualityGateConfig, DedupeConfig, UpscaleConfig, VaeGateConfig,
    CaptionConfig, AuditConfig, ConfigGenConfig, BucketDryRunConfig,
)


def _invoke_QualityGateStep(working_dir: Path, output_dir: Path, cfg: QualityGateConfig,
                             *, original_dir: Path, **_kw) -> None:
    from .steps import s1_source
    if working_dir.exists():
        shutil.rmtree(working_dir)
    s1_source.run(
        original_dir, working_dir,
        auto_only=cfg.auto_only,
        manual_all=cfg.manual_all,
        scorers=[dataclasses.asdict(s) for s in cfg.scorers],
        report_path=output_dir / "reports" / "QualityGateStep_report.json",
        interaction=_kw.get("interaction"),
    )


def _invoke_DedupeStep(working_dir: Path, output_dir: Path, cfg: DedupeConfig,
                        **_kw) -> None:
    from .steps import s2_curate
    s2_curate.run(
        working_dir,
        output_dir=working_dir,
        auto_dedupe=True,
        skip_clip=False,
        report_path=output_dir / "reports" / "DedupeStep_report.json",
    )


def _invoke_UpscaleStep(working_dir: Path, output_dir: Path, cfg: UpscaleConfig,
                         **_kw) -> None:
    from .steps import s3_upscale
    s3_upscale.run(
        working_dir,
        output_dir=working_dir,
        upscale_target=cfg.upscale_target,
        upscale_model=cfg.upscale_model,
        hallucination_ssim_threshold=cfg.hallucination_ssim_threshold,
        report_path=output_dir / "reports" / "UpscaleStep_report.json",
    )


def _invoke_VaeGateStep(working_dir: Path, output_dir: Path, cfg: VaeGateConfig,
                         *, network, **_kw) -> None:
    from .steps import s4_vae_gate
    s4_vae_gate.run(
        working_dir,
        network=network,
        output_dir=working_dir,
        outlier_sigma=cfg.outlier_sigma,
        report_path=output_dir / "reports" / "VaeGateStep_report.json",
    )


def _invoke_CaptionStep(working_dir: Path, output_dir: Path, cfg: CaptionConfig,
                         *, concept_token: Optional[str], **_kw) -> None:
    from .steps import s5_caption
    runtime = _kw.get("caption_runtime") or {}
    qwen_model_id = runtime.get("model_id") or cfg.qwen_model_id
    quantization = runtime.get("vram_mode") or cfg.quantization
    s5_caption.run(
        working_dir,
        concept_token=concept_token,
        output_dir=working_dir,
        qwen_model_id=qwen_model_id,
        quantization=quantization,
        dtype=cfg.dtype,
        max_new_tokens=cfg.max_new_tokens,
        spot_check_pct=cfg.spot_check_pct,
        overwrite=bool(_kw.get("force", False)),
        report_path=output_dir / "reports" / "CaptionStep_report.json",
        interaction=_kw.get("interaction"),
    )


def _invoke_AuditStep(working_dir: Path, output_dir: Path, cfg: AuditConfig,
                       *, network, **_kw) -> dict:
    from .steps import s6_audit
    return s6_audit.run(
        working_dir,
        network=network,
        report_path=output_dir / "reports" / "AuditStep_report.json",
    )


def _invoke_ConfigGenStep(working_dir: Path, output_dir: Path, cfg: ConfigGenConfig,
                           *, network, concept_token: Optional[str],
                           network_type: Optional[str] = None, **_kw) -> None:
    from .steps import s7_config
    s7_config.run(
        working_dir,
        network=network,
        concept_token=concept_token,
        output_dir=output_dir,
        network_type=network_type,
        report_path=output_dir / "reports" / "ConfigGenStep_report.json",
    )


def _invoke_BucketDryRunStep(working_dir: Path, output_dir: Path, cfg: BucketDryRunConfig,
                              *, network, **_kw) -> None:
    from .steps import s8_bucket
    s8_bucket.run(
        working_dir,
        network=network,
        output_dir=output_dir,
        cache_mode=cfg.cache_mode,
        thin_threshold=cfg.thin_threshold,
        report_path=output_dir / "reports" / "BucketDryRunStep_report.json",
    )


STEP_INVOKE_MAP: dict[str, Callable] = {
    "QualityGateStep":  _invoke_QualityGateStep,
    "DedupeStep":       _invoke_DedupeStep,
    "UpscaleStep":      _invoke_UpscaleStep,
    "VaeGateStep":      _invoke_VaeGateStep,
    "CaptionStep":      _invoke_CaptionStep,
    "AuditStep":        _invoke_AuditStep,
    "ConfigGenStep":    _invoke_ConfigGenStep,
    "BucketDryRunStep": _invoke_BucketDryRunStep,
}
