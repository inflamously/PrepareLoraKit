"""Public orchestration entry point for VaeGateStep."""
from __future__ import annotations

import shutil
from pathlib import Path

from prepare_lora_kit.cancellation import check_cancel
from prepare_lora_kit.pipeline.configs import VaeGateConfig
from prepare_lora_kit.report import reporter, step_report_path
from prepare_lora_kit.steps.context import StepRunContext
from prepare_lora_kit.steps.vae_gate.artifacts import (
    _materialize_with_captions,
    _prune_unrequested_artifacts,
)
from prepare_lora_kit.steps.vae_gate.reconstruction import (
    _PreviewOptions,
    _reconstruct_all,
    _ReconstructionPass,
)
from prepare_lora_kit.steps.vae_gate.reports import _build_success_report, _save_skipped_report
from prepare_lora_kit.steps.vae_gate.review_flow import (
    _review_reconstructions,
    _reviewed_items,
    _select_survivors,
)
from prepare_lora_kit.steps.vae_gate.vae import _load_vae
from prepare_lora_kit.utils import image as img_utils
from prepare_lora_kit.utils.accelerator import release_accelerator_memory

_DEFAULT_SUBSTEPS = (
    "reconstruct_images",
    "review_vae_artifacts",
    "apply_vae_decisions",
)


def run(
    dataset_dir: Path,
    config: VaeGateConfig,
    *,
    context: StepRunContext | None = None,
) -> dict:
    """Reconstruct, review, and apply VAE artifact decisions to a dataset."""
    context = context or StepRunContext()
    reporter.step_header("VAE Reconstruction Gate")
    enabled = set(context.enabled_substeps or _DEFAULT_SUBSTEPS)
    output_dir = context.output_dir or dataset_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    target_report = context.report_path or step_report_path(output_dir, "VaeGateStep")
    preview_root = (
        (context.report_path.parent if context.report_path else output_dir)
        / "VaeGateStep_previews"
    )
    if preview_root.exists():
        shutil.rmtree(preview_root)

    images = img_utils.iter_images(dataset_dir)
    if not images:
        reporter.warn(f"No images in {dataset_dir}")
        return _save_skipped_report(
            "no images", enabled, config.outlier_sigma, target_report
        )

    if "reconstruct_images" not in enabled:
        reporter.info("VAE reconstruction substep disabled; passing through originals.")
        _materialize_with_captions(images, images, dataset_dir, output_dir)
        return _save_skipped_report(
            "reconstruct_images disabled", enabled, config.outlier_sigma, target_report
        )

    interactive_review = (
        "review_vae_artifacts" in enabled and context.interaction is not None
    )
    recon, load_error = _load_and_reconstruct(
        images,
        config,
        preview_root,
        interactive_review=interactive_review,
        cancel_check=context.cancel_check,
    )
    if recon is None:
        assert load_error is not None
        return _save_skipped_report(
            load_error,
            enabled,
            config.outlier_sigma,
            target_report,
            failed=len(images),
            failures=[{"stage": "load", "path": None, "error": load_error}],
        )

    review = _review_reconstructions(
        images,
        recon,
        config.outlier_sigma,
        enabled,
        context.interaction,
        context.cancel_check,
    )
    if interactive_review:
        _prune_unrequested_artifacts(
            recon.review_artifacts,
            preview_root,
            keep_vae=config.output_previews,
            keep_diff=config.output_silhouettes,
            keep_hard=config.output_hard_silhouettes,
        )

    survivors = _select_survivors(
        images,
        review.decisions,
        apply_decisions="apply_vae_decisions" in enabled,
    )
    check_cancel(context.cancel_check)
    _materialize_with_captions(images, survivors, dataset_dir, output_dir)

    reviewed = _reviewed_items(
        review.items, review.decisions, context.cancel_check
    )
    report_data = _build_success_report(
        recon, review, reviewed, config.outlier_sigma, enabled
    )
    check_cancel(context.cancel_check)
    reporter.save_report(report_data, target_report)
    return report_data


def _load_and_reconstruct(
    images: list[Path],
    config: VaeGateConfig,
    preview_root: Path,
    *,
    interactive_review: bool,
    cancel_check,
) -> tuple[_ReconstructionPass | None, str | None]:
    reporter.info(f"Loading VAE from {config.vae_model_id} …")
    check_cancel(cancel_check)
    try:
        vae, device, dtype = _load_vae(config.vae_model_id, config.vae_config_id)
    except Exception as exc:
        reporter.error(f"VAE load failed: {exc}")
        reporter.warn("VAE gate could not assess the dataset; all inputs remain unchanged.")
        return None, str(exc)

    try:
        previews = _PreviewOptions(
            diff_amplification=config.diff_amplification,
            gaussian_blur_sigma=config.gaussian_blur_sigma,
            gaussian_blur_kernel=config.gaussian_blur_kernel,
            otsu_enabled=config.otsu_enabled,
            write_vae=config.output_previews or interactive_review,
            write_diff=config.output_silhouettes or interactive_review,
            write_hard=config.output_hard_silhouettes or interactive_review,
        )
        reporter.info(
            f"Reconstructing {len(images)} images "
            f"(device={device}, max_side={config.max_side}) …"
        )
        recon = _reconstruct_all(
            images,
            vae,
            device,
            dtype,
            preview_root,
            previews,
            max_side=config.max_side,
            seed=config.seed,
            hf_cutoff_fraction=config.hf_cutoff_fraction,
            cancel_check=cancel_check,
        )
        return recon, None
    finally:
        del vae
        release_accelerator_memory()
