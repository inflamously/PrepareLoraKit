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
    QualityGateConfig, CurateConfig, UpscaleConfig, VaeGateConfig,
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


def _invoke_CurateStep(working_dir: Path, output_dir: Path, cfg: CurateConfig,
                        **_kw) -> None:
    if _kw.get("mock_runtime"):
        return _mock_curate(
            working_dir,
            output_dir,
            cfg,
            coverage_mode=str(_kw.get("mock_curate_coverage") or "auto"),
        )

    from .steps import s2_curate
    return s2_curate.run(
        working_dir,
        output_dir=working_dir,
        auto_dedupe=True,
        skip_clip=cfg.skip_clip,
        report_path=output_dir / "reports" / "CurateStep_report.json",
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
    if _kw.get("mock_runtime"):
        _mock_vae_gate(working_dir, output_dir, interaction=_kw.get("interaction"))
        return

    from .steps import s4_vae_gate
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
    )


def _invoke_CaptionStep(working_dir: Path, output_dir: Path, cfg: CaptionConfig,
                         *, concept_token: Optional[str], **_kw) -> None:
    if _kw.get("mock_runtime"):
        _mock_caption(
            working_dir,
            output_dir,
            concept_token=concept_token,
            interaction=_kw.get("interaction"),
            force=bool(_kw.get("force", False)),
        )
        return

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
    "CurateStep":       _invoke_CurateStep,
    "UpscaleStep":      _invoke_UpscaleStep,
    "VaeGateStep":      _invoke_VaeGateStep,
    "CaptionStep":      _invoke_CaptionStep,
    "AuditStep":        _invoke_AuditStep,
    "ConfigGenStep":    _invoke_ConfigGenStep,
    "BucketDryRunStep": _invoke_BucketDryRunStep,
}


def _mock_curate(
    working_dir: Path,
    output_dir: Path,
    cfg: CurateConfig,
    *,
    coverage_mode: str = "auto",
) -> dict:
    from .steps.s2_curate.coverage import _save_pca, _save_umap
    from .steps.s2_curate.dedupe import _compute_hashes, _find_duplicates, _resolve_duplicates
    from .utils import image as img_utils
    from .utils import report as rpt

    rpt.step_header(2, "Curation — Mock Runtime")
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "CurateStep_report.json"

    images = img_utils.iter_images(working_dir)
    if not images:
        rpt.warn(f"No images in {working_dir}")
        return {}

    hashes = _compute_hashes(images)
    pairs = _find_duplicates(hashes)
    to_drop = _resolve_duplicates(pairs, auto_drop=True) if pairs else set()
    kept_images = [p for p in images if p not in to_drop]
    img_utils.materialize(kept_images, working_dir, working_dir)

    coverage_path: Path | None = None
    coverage_metadata: dict | None = None
    mode = coverage_mode.lower().strip()
    if mode not in {"auto", "pca", "umap"}:
        mode = "auto"

    if len(kept_images) >= 2:
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
        "occluded_flagged": [],
        "coverage_image": str(coverage_path) if coverage_path else None,
        "coverage": coverage_metadata,
    }
    rpt.info(f"Mock runtime: curated {len(kept_images)} image(s).")
    rpt.save_report(report, report_path)
    return report


def _mock_embeddings(paths: list[Path]) -> "np.ndarray":
    import numpy as np

    rows = []
    total = max(1, len(paths) - 1)
    for index, path in enumerate(paths):
        t = index / total
        name_value = (sum(path.name.encode("utf-8")) % 97) / 97.0
        rows.append([
            t,
            t * t,
            np.sin(t * np.pi * 2.0),
            np.cos(t * np.pi * 2.0),
            name_value,
            (index % 5) / 5.0,
            (index % 7) / 7.0,
            1.0,
        ])
    return np.asarray(rows, dtype=np.float32)


def _mock_vae_gate(working_dir: Path, output_dir: Path, *, interaction=None) -> dict:
    from .utils import image as img_utils
    from .utils import report as rpt
    from .steps.s4_vae_gate.review import _save_review_artifacts
    import numpy as np
    from PIL import Image, ImageFilter

    rpt.step_header(4, "VAE Reconstruction Gate")
    images = img_utils.iter_images(working_dir)
    scores = {str(path): 0.0 for path in images}
    preview_root = output_dir / "reports" / "VaeGateStep_previews"
    review_items = []
    for index, path in enumerate(images):
        with Image.open(path).convert("RGB") as img:
            recon = img.filter(ImageFilter.GaussianBlur(radius=1.6 if index == 0 else 0.6))
            recon_arr = np.array(recon)
        artifact = _save_review_artifacts(path, recon_arr, preview_root)
        review_items.append({
            "path": str(path),
            "name": path.name,
            "width": artifact["width"],
            "height": artifact["height"],
            "hf_loss": 0.0,
            "threshold": 0.0,
            "diff_threshold": artifact["diff_threshold"],
            "flagged": False,
            "initial_decision": "keep",
            "views": artifact["views"],
        })

    decisions = interaction.vae_review(review_items) if interaction and review_items else {}
    survivors = [
        path for path in images
        if decisions.get(str(path), decisions.get(str(path.resolve()), "keep")) != "drop"
    ]
    img_utils.materialize(survivors, working_dir, working_dir)
    report = {
        "mock_runtime": True,
        "hf_scores": scores,
        "threshold": 0.0,
        "flagged": [],
        "review_items": [
            {
                **item,
                "decision": decisions.get(
                    item["path"],
                    decisions.get(str(Path(item["path"]).resolve()), "keep"),
                ),
            }
            for item in review_items
        ],
        "needs_replacement": [
            str(path)
            for path in images
            if decisions.get(str(path), decisions.get(str(path.resolve()), "keep")) == "replace"
        ],
    }
    rpt.info(f"Mock runtime: recorded deterministic VAE pass for {len(images)} image(s).")
    rpt.save_report(report, output_dir / "reports" / "VaeGateStep_report.json")
    return report


def _mock_caption(
    working_dir: Path,
    output_dir: Path,
    *,
    concept_token: Optional[str],
    interaction,
    force: bool,
) -> dict:
    from .interaction import CliInteractionProvider
    from .utils import image as img_utils
    from .utils import report as rpt

    rpt.step_header(5, "Caption — Mock Runtime")
    working_dir.mkdir(parents=True, exist_ok=True)
    provider = interaction or CliInteractionProvider()
    images = img_utils.iter_images(working_dir)
    token_prefix = f"{concept_token}, " if concept_token else ""

    captions: dict[str, str] = {}
    annotation_log: dict[str, list] = {}
    skipped_annotation: list[str] = []
    skip_all = False

    def _region_captioner(_crop, _metadata=None):
        return {"caption": f"{token_prefix}mock region caption".strip(", ")}

    for path in images:
        txt_path = path.with_suffix(".txt")
        if txt_path.exists() and not force:
            captions[str(path)] = txt_path.read_text(encoding="utf-8").strip()
            rpt.info(f"Skip (exists): {path.name}")
            continue

        if skip_all:
            annotations, skipped = [], True
        else:
            annotations, skipped, skip_all = provider.annotate_image(
                path,
                captioner=_region_captioner,
            )
        annotation_log[str(path)] = annotations
        if skipped:
            skipped_annotation.append(str(path))

        caption = f"{token_prefix}mock caption for {path.stem}".strip()
        txt_path.write_text(caption, encoding="utf-8")
        captions[str(path)] = caption
        rpt.ok(f"{path.name} -> {caption}")

    report = {
        "mock_runtime": True,
        "total": len(images),
        "captioned": len(captions),
        "annotations": annotation_log,
        "skipped_annotation": skipped_annotation,
        "missing_token": [],
        "short_captions": [],
        "long_captions": [],
        "spot_check_sample": [],
    }
    rpt.save_report(report, output_dir / "reports" / "CaptionStep_report.json")
    return report
