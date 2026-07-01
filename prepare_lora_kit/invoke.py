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

from .cancellation import check_cancel
from .project.configs import (
    ImportConfig,
    QualityGateConfig, CurateConfig, UpscaleConfig, VaeGateConfig,
    CaptionConfig, AuditConfig, ConfigGenConfig, BucketDryRunConfig, ExportConfig,
)


def _invoke_ImportStep(working_dir: Path, output_dir: Path, cfg: ImportConfig,
                       *, original_dir: Path, **_kw) -> dict:
    from .steps import s0_import
    if working_dir.exists():
        shutil.rmtree(working_dir)
    check_cancel(_kw.get("cancel_check"))
    return s0_import.run(
        original_dir,
        working_dir,
        report_path=output_dir / "reports" / "ImportStep_report.json",
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
    )


def _invoke_QualityGateStep(working_dir: Path, output_dir: Path, cfg: QualityGateConfig,
                            *, original_dir: Path, **_kw) -> None:
    from .steps import s1_source
    _require_working_dataset(working_dir)
    s1_source.run(
        working_dir,
        working_dir,
        auto_only=cfg.auto_only,
        manual_all=cfg.manual_all,
        scorers=[dataclasses.asdict(s) for s in cfg.scorers],
        report_path=output_dir / "reports" / "QualityGateStep_report.json",
        interaction=_kw.get("interaction"),
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
    )


def _invoke_CurateStep(working_dir: Path, output_dir: Path, cfg: CurateConfig,
                       **_kw) -> None:
    _require_working_dataset(working_dir)
    if _kw.get("mock_runtime"):
        return _mock_curate(
            working_dir,
            output_dir,
            cfg,
            coverage_mode=str(_kw.get("mock_curate_coverage") or "auto"),
            enabled_substeps=_kw.get("enabled_substeps"),
            cancel_check=_kw.get("cancel_check"),
        )

    from .steps import s2_curate
    return s2_curate.run(
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


def _invoke_UpscaleStep(working_dir: Path, output_dir: Path, cfg: UpscaleConfig,
                        **_kw) -> None:
    _require_working_dataset(working_dir)
    from .steps import s3_upscale
    s3_upscale.run(
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


def _invoke_VaeGateStep(working_dir: Path, output_dir: Path, cfg: VaeGateConfig,
                        *, network, **_kw) -> None:
    _require_working_dataset(working_dir)
    if _kw.get("mock_runtime"):
        _mock_vae_gate(
            working_dir,
            output_dir,
            interaction=_kw.get("interaction"),
            enabled_substeps=_kw.get("enabled_substeps"),
            cancel_check=_kw.get("cancel_check"),
        )
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
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
    )


def _invoke_CaptionStep(working_dir: Path, output_dir: Path, cfg: CaptionConfig,
                        *, concept_token: Optional[str], **_kw) -> None:
    _require_working_dataset(working_dir)
    if _kw.get("mock_runtime"):
        _mock_caption(
            working_dir,
            output_dir,
            concept_token=concept_token,
            force=bool(_kw.get("force", False)),
            enabled_substeps=_kw.get("enabled_substeps"),
            cancel_check=_kw.get("cancel_check"),
            interaction=_kw.get("interaction"),
        )
        return

    from .steps import s5_caption
    runtime = _kw.get("caption_runtime") or {}
    caption_model_id = runtime.get("model_id") or cfg.caption_model_id
    caption_model_task = runtime.get("task") or cfg.caption_model_task
    quantization = runtime.get("vram_mode") or cfg.quantization
    s5_caption.run(
        working_dir,
        concept_token=concept_token,
        output_dir=working_dir,
        caption_model_id=caption_model_id,
        caption_model_task=caption_model_task,
        quantization=quantization,
        dtype=cfg.dtype,
        max_new_tokens=cfg.max_new_tokens,
        spot_check_pct=cfg.spot_check_pct,
        overwrite=bool(_kw.get("force", False)),
        report_path=output_dir / "reports" / "CaptionStep_report.json",
        interaction=_kw.get("interaction"),
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
        caption_status_callback=_kw.get("caption_status_callback"),
        caption_prompt=cfg.caption_prompt,
        region_prompt=cfg.region_prompt,
    )


def _invoke_AuditStep(working_dir: Path, output_dir: Path, cfg: AuditConfig,
                      *, network, **_kw) -> dict:
    _require_working_dataset(working_dir)
    from .steps import s6_audit
    return s6_audit.run(
        working_dir,
        network=network,
        report_path=output_dir / "reports" / "AuditStep_report.json",
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
    )


def _invoke_ConfigGenStep(working_dir: Path, output_dir: Path, cfg: ConfigGenConfig,
                          *, network, concept_token: Optional[str],
                          network_type: Optional[str] = None, **_kw) -> None:
    _require_working_dataset(working_dir)
    from .steps import s7_config
    s7_config.run(
        working_dir,
        network=network,
        concept_token=concept_token,
        output_dir=output_dir,
        network_type=network_type,
        report_path=output_dir / "reports" / "ConfigGenStep_report.json",
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
    )


def _invoke_BucketDryRunStep(working_dir: Path, output_dir: Path, cfg: BucketDryRunConfig,
                             *, network, **_kw) -> None:
    _require_working_dataset(working_dir)
    from .steps import s8_bucket
    s8_bucket.run(
        working_dir,
        network=network,
        output_dir=output_dir,
        cache_mode=cfg.cache_mode,
        thin_threshold=cfg.thin_threshold,
        report_path=output_dir / "reports" / "BucketDryRunStep_report.json",
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
    )


def _invoke_ExportStep(working_dir: Path, output_dir: Path, cfg: ExportConfig,
                       *, original_dir: Path | None = None, **_kw) -> dict:
    _require_working_dataset(working_dir)
    from .steps import s9_export
    return s9_export.run(
        working_dir,
        original_dir=original_dir,
        target_dir=cfg.target_dir,
        output_dir=output_dir,
        interaction=_kw.get("interaction"),
        report_path=output_dir / "reports" / "ExportStep_report.json",
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
    )


STEP_INVOKE_MAP: dict[str, Callable] = {
    "ImportStep": _invoke_ImportStep,
    "QualityGateStep": _invoke_QualityGateStep,
    "CurateStep": _invoke_CurateStep,
    "UpscaleStep": _invoke_UpscaleStep,
    "VaeGateStep": _invoke_VaeGateStep,
    "CaptionStep": _invoke_CaptionStep,
    "AuditStep": _invoke_AuditStep,
    "ConfigGenStep": _invoke_ConfigGenStep,
    "BucketDryRunStep": _invoke_BucketDryRunStep,
    "ExportStep": _invoke_ExportStep,
}


def _require_working_dataset(working_dir: Path) -> None:
    if not working_dir.exists():
        raise FileNotFoundError(f"Working dataset does not exist at {working_dir}. Run ImportStep first.")


def _mock_curate(
        working_dir: Path,
        output_dir: Path,
        cfg: CurateConfig,
        *,
        coverage_mode: str = "auto",
        enabled_substeps: list[str] | None = None,
        cancel_check=None,
) -> dict:
    from .steps.s2_curate.coverage import _save_pca, _save_umap
    from .steps.s2_curate.dedupe import _compute_hashes, _find_duplicates
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


def _mock_embeddings(paths: list[Path]) -> "np.ndarray":
    import numpy as np

    centers = np.asarray([
        [0.0, 0.0, 0.0, 1.0, 0.20, 0.10, 0.0, 1.0],
        [1.2, 0.2, 0.9, 0.1, 0.65, 0.25, 0.3, 1.0],
        [0.2, 1.1, 0.1, 0.8, 0.35, 0.80, 0.6, 1.0],
    ], dtype=np.float32)
    rows = []
    for index, path in enumerate(paths):
        name_value = (sum(path.name.encode("utf-8")) % 97) / 97.0
        if path.name.startswith(("mock_pca_", "mock_umap_")):
            cluster = index % len(centers)
            jitter = ((index // len(centers)) % 5 - 2) * 0.012
            row = centers[cluster].copy()
            row += np.asarray([
                jitter,
                -jitter,
                jitter * 0.5,
                -jitter * 0.5,
                name_value * 0.01,
                jitter * 0.25,
                -jitter * 0.25,
                0.0,
            ], dtype=np.float32)
        else:
            t = index / max(1, len(paths) - 1)
            row = np.asarray([
                2.0 + t,
                -0.8 + t * 0.4,
                np.sin(t * np.pi * 2.0),
                np.cos(t * np.pi * 2.0),
                name_value,
                (index % 5) / 5.0,
                (index % 7) / 7.0,
                1.0,
            ], dtype=np.float32)
        rows.append(row)
    return np.asarray(rows, dtype=np.float32)


def _mock_vae_gate(
        working_dir: Path,
        output_dir: Path,
        *,
        interaction=None,
        enabled_substeps: list[str] | None = None,
        cancel_check=None,
) -> dict:
    from .utils import image as img_utils
    from .utils import report as rpt
    from .steps.s4_vae_gate.review import _save_review_artifacts
    import numpy as np
    from PIL import Image, ImageFilter

    rpt.step_header(4, "VAE Reconstruction Gate")
    enabled = set(enabled_substeps or ["s4_1_reconstruct", "s4_2_review", "s4_3_apply_decisions"])
    images = img_utils.iter_images(working_dir)
    scores = {str(path): 0.0 for path in images}
    preview_root = output_dir / "reports" / "VaeGateStep_previews"
    review_items = []
    for index, path in enumerate(images):
        check_cancel(cancel_check)
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

    check_cancel(cancel_check)
    decisions = (
        interaction.vae_review(review_items)
        if "s4_2_review" in enabled and interaction and review_items
        else {}
    )
    check_cancel(cancel_check)
    survivors = [
        path for path in images
        if "s4_3_apply_decisions" not in enabled
           or decisions.get(str(path), decisions.get(str(path.resolve()), "keep")) != "drop"
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
        "substeps": {
            "s4_1_reconstruct": {"enabled": "s4_1_reconstruct" in enabled},
            "s4_2_review": {"enabled": "s4_2_review" in enabled},
            "s4_3_apply_decisions": {"enabled": "s4_3_apply_decisions" in enabled},
        },
    }
    rpt.info(f"Mock runtime: recorded deterministic VAE pass for {len(images)} image(s).")
    check_cancel(cancel_check)
    rpt.save_report(report, output_dir / "reports" / "VaeGateStep_report.json")
    return report


def _mock_caption(
        working_dir: Path,
        output_dir: Path,
        *,
        concept_token: Optional[str],
        force: bool,
        enabled_substeps: list[str] | None = None,
        cancel_check=None,
        interaction=None,
) -> dict:
    from .utils import image as img_utils
    from .utils import report as rpt
    from .interaction import annotate_dataset_via_images
    from .steps.s5_caption.artifacts import (
        _is_bbox_artifact,
        _save_bbox_training_item,
        load_boxes_sidecar,
        save_boxes_sidecar,
    )

    rpt.step_header(5, "Caption — Mock Runtime")
    enabled = set(enabled_substeps or ["s5_1_annotate", "s5_2_caption", "s5_3_validate"])
    working_dir.mkdir(parents=True, exist_ok=True)
    images = [p for p in img_utils.iter_images(working_dir) if not _is_bbox_artifact(p)]
    token_prefix = f"{concept_token}, " if concept_token else ""

    # Resume: only images that still lack a caption need work (``force`` recaptions
    # everything). Already-captioned images and their hand-drawn boxes are left
    # untouched, mirroring steps/s5_caption/step.py.
    pending = [p for p in images if force or not p.with_suffix(".txt").exists()]
    pending_set = set(pending)

    # Mirror steps/s5_caption/regions.py::make_region_captioner but caption the
    # cropped region with deterministic mock text instead of a VLM, so the UI
    # "Caption selected box" button works end-to-end under --mock.
    def mock_region_captioner(crop, metadata=None):
        check_cancel(cancel_check)
        source_raw = (metadata or {}).get("source_path") or (metadata or {}).get("image_path")
        if not source_raw:
            raise ValueError("Region caption metadata missing source_path")
        source_path = Path(source_raw)
        text = f"mock region caption for {source_path.stem}"
        return _save_bbox_training_item(crop, source_path, output_dir, text, concept_token)

    captions: dict[str, str] = {}
    annotation_log: dict[str, list] = {}
    skipped_annotation: list[str] = []

    # Preserve already-captioned images so the report stays complete on a resume.
    for path in images:
        if path in pending_set:
            continue
        txt_path = path.with_suffix(".txt")
        if txt_path.exists():
            captions[str(path)] = txt_path.read_text(encoding="utf-8").strip()

    # Phase A — gather decisions via the same batch interaction the real step uses
    # (steps/s5_caption/workflow.py::gather_decisions), for the pending images only.
    # Headless/CLI mock has no provider, so every pending image captions with no
    # regions; a resume with nothing pending never pops an empty modal.
    if not pending or "s5_2_caption" not in enabled:
        decisions: dict[str, dict] = {}
    elif "s5_1_annotate" not in enabled or interaction is None:
        decisions = {str(p): {"annotations": [], "skipped": False} for p in pending}
    else:
        descriptors = [
            {
                "path": path,
                "name": path.name,
                "annotations": load_boxes_sidecar(path),
                "done": path.with_suffix(".txt").exists() and not force,
            }
            for path in pending
        ]
        annotate = getattr(interaction, "annotate_dataset", None)
        if annotate is not None:
            decisions, _skip_all = annotate(descriptors, captioner=mock_region_captioner)
        else:
            decisions, _skip_all = annotate_dataset_via_images(
                interaction, descriptors, captioner=mock_region_captioner,
            )

    # Phase B — caption each pending, non-skipped image with deterministic mock text.
    for path in pending:
        check_cancel(cancel_check)
        txt_path = path.with_suffix(".txt")
        decision = decisions.get(str(path))

        if "s5_2_caption" not in enabled:
            if txt_path.exists():
                captions[str(path)] = txt_path.read_text(encoding="utf-8").strip()
            continue

        if decision is None or decision.get("skipped"):
            if txt_path.exists() and not force:
                captions[str(path)] = txt_path.read_text(encoding="utf-8").strip()
                rpt.info(f"Skip (keep existing): {path.name}")
            skipped_annotation.append(str(path))
            continue

        annotations = decision.get("annotations") or []
        annotation_log[str(path)] = annotations
        if not annotations:
            skipped_annotation.append(str(path))
        save_boxes_sidecar(path, annotations)

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
        "substeps": {
            "s5_1_annotate": {"enabled": "s5_1_annotate" in enabled},
            "s5_2_caption": {"enabled": "s5_2_caption" in enabled},
            "s5_3_validate": {"enabled": "s5_3_validate" in enabled},
        },
    }
    check_cancel(cancel_check)
    rpt.save_report(report, output_dir / "reports" / "CaptionStep_report.json")
    return report
