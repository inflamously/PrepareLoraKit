"""
Step 4 — VAE Reconstruction Gate

Encodes each image through the target model's VAE, decodes back, and measures
high-frequency loss via FFT spectrum comparison. Outliers (> mean + 2σ) are
flagged for a manual keep / drop decision. Reconstructions are diagnostics only.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from prepare_lora_kit.cancellation import CancelCheck, CancelledRun, check_cancel
from prepare_lora_kit.providers.interaction import InteractionProvider
from prepare_lora_kit.report import reporter
from prepare_lora_kit.steps.vae_gate.hf_loss import _hf_loss
from prepare_lora_kit.steps.vae_gate.review import _manual_flag_decision, _save_review_artifacts
from prepare_lora_kit.steps.vae_gate.vae import _encode_decode, _load_vae, _to_lab_l
from prepare_lora_kit.utils import image as img_utils

# ── Main ──────────────────────────────────────────────────────────────────────

def run(
    dataset_dir: Path,
    vae_model_id: str,
    vae_config_id: str | None = None,
    output_dir: Path | None = None,
    outlier_sigma: float = 2.0,
    report_path: Path | None = None,
    interaction: InteractionProvider | None = None,
    diff_amplification: float = 4.0,
    gaussian_blur_sigma: float = 2.0,
    gaussian_blur_kernel: int = 21,
    otsu_enabled: bool = True,
    output_previews: bool = True,
    output_silhouettes: bool = True,
    output_hard_silhouettes: bool = True,
    max_side: int | None = None,
    hf_cutoff_fraction: float = 0.25,
    seed: int = 42,
    enabled_substeps: list[str] | None = None,
    cancel_check: CancelCheck | None = None,
) -> dict:
    reporter.step_header("VAE Reconstruction Gate")
    enabled = set(enabled_substeps or [
        "reconstruct_images",
        "review_vae_artifacts",
        "apply_vae_decisions",
    ])

    output_dir = output_dir or dataset_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    target_report = report_path or (output_dir / "step4_report.json")
    preview_root = (
        (report_path.parent if report_path else output_dir) / "VaeGateStep_previews"
    )
    if preview_root.exists():
        shutil.rmtree(preview_root)

    images = img_utils.iter_images(dataset_dir)
    if not images:
        reporter.warn(f"No images in {dataset_dir}")
        return _save_skipped_report("no images", enabled, outlier_sigma, target_report)

    if "reconstruct_images" not in enabled:
        reporter.info("VAE reconstruction substep disabled; passing through originals.")
        _materialize_with_captions(images, images, dataset_dir, output_dir)
        return _save_skipped_report(
            "reconstruct_images disabled", enabled, outlier_sigma, target_report)

    reporter.info(f"Loading VAE from {vae_model_id} …")
    check_cancel(cancel_check)
    try:
        vae, device, dtype = _load_vae(vae_model_id, vae_config_id)
    except Exception as exc:
        reporter.error(f"VAE load failed: {exc}")
        reporter.warn("VAE gate could not assess the dataset; all inputs remain unchanged.")
        return _save_skipped_report(
            str(exc), enabled, outlier_sigma, target_report,
            failed=len(images),
            failures=[{"stage": "load", "path": None, "error": str(exc)}],
        )

    reporter.info(
        f"Reconstructing {len(images)} images (device={device}, max_side={max_side}) …")

    interactive_review = "review_vae_artifacts" in enabled and interaction is not None
    previews = _PreviewOptions(
        diff_amplification=diff_amplification,
        gaussian_blur_sigma=gaussian_blur_sigma,
        gaussian_blur_kernel=gaussian_blur_kernel,
        otsu_enabled=otsu_enabled,
        write_vae=output_previews or interactive_review,
        write_diff=output_silhouettes or interactive_review,
        write_hard=output_hard_silhouettes or interactive_review,
    )
    recon = _reconstruct_all(
        images, vae, device, dtype, preview_root, previews,
        max_side=max_side,
        seed=seed,
        hf_cutoff_fraction=hf_cutoff_fraction,
        cancel_check=cancel_check,
    )

    mean, std, threshold = _threshold_stats(recon.hf_scores, outlier_sigma)
    flagged = [
        p for p, score in recon.hf_scores.items()
        if threshold is not None and score > threshold
    ]
    reporter.warn(f"{len(flagged)} images flagged as high-frequency-loss outliers")

    review_items = _build_review_items(images, recon, threshold, set(flagged), cancel_check)
    decisions = _collect_decisions(
        enabled, interaction, review_items, flagged, recon, cancel_check)

    if interactive_review:
        _prune_unrequested_artifacts(
            recon.review_artifacts,
            preview_root,
            keep_vae=output_previews,
            keep_diff=output_silhouettes,
            keep_hard=output_hard_silhouettes,
        )

    survivors = (
        [path for path in images if _decision_for(decisions, path) != "drop"]
        if "apply_vae_decisions" in enabled
        else list(images)
    )
    check_cancel(cancel_check)
    _materialize_with_captions(images, survivors, dataset_dir, output_dir)

    reviewed = []
    for item in review_items:
        check_cancel(cancel_check)
        path = Path(str(item["path"]))
        decision = _decision_for(decisions, path)
        reviewed.append({**item, "decision": decision})
        if decision != "keep":
            reporter.info(f"  {path.name} → {decision}")

    report_data = {
        "hf_scores": {k: round(v, 5) for k, v in recon.hf_scores.items()},
        "threshold": _rounded(threshold),
        "statistics": _statistics(
            len(recon.hf_scores), len(recon.failures), mean, std, threshold, outlier_sigma
        ),
        "flagged": [
            {"path": p,
             "hf_loss": round(recon.hf_scores[p], 5),
             "decision": _decision_for(decisions, Path(p))}
            for p in flagged
        ],
        "failures": recon.failures,
        "review_items": reviewed,
        "substeps": _substep_report(enabled),
    }
    check_cancel(cancel_check)
    reporter.save_report(report_data, target_report)
    return report_data


@dataclass(frozen=True)
class _PreviewOptions:
    """Which review artifacts to render, and how.

    ``write_*`` are wider than the caller's ``output_*`` flags whenever an
    interactive review is running: the gallery needs every view even when the
    project only wants some of them persisted. :func:`_prune_unrequested_artifacts`
    deletes the surplus once the review is done.
    """

    diff_amplification: float
    gaussian_blur_sigma: float
    gaussian_blur_kernel: int
    otsu_enabled: bool
    write_vae: bool
    write_diff: bool
    write_hard: bool

    @property
    def writes_anything(self) -> bool:
        return self.write_vae or self.write_diff or self.write_hard


@dataclass
class _ReconstructionPass:
    """What one encode/decode sweep over the dataset produced."""

    hf_scores: dict[str, float] = field(default_factory=dict)
    reconstructions: dict[str, np.ndarray] = field(default_factory=dict)
    review_artifacts: dict[str, dict] = field(default_factory=dict)
    failures: list[dict] = field(default_factory=list)


def _save_skipped_report(
    reason: str,
    enabled: set[str],
    outlier_sigma: float,
    target_report: Path,
    *,
    failed: int = 0,
    failures: list[dict] | None = None,
) -> dict:
    """Write and return the report shape used when nothing was assessed."""
    report_data = {
        "skipped": True,
        "reason": reason,
        "hf_scores": {},
        "threshold": None,
        "statistics": _statistics(0, failed, None, None, None, outlier_sigma),
        "flagged": [],
        "failures": failures or [],
        "review_items": [],
        "substeps": _substep_report(enabled),
    }
    reporter.save_report(report_data, target_report)
    return report_data


def _reconstruct_all(
    images: list[Path],
    vae,
    device,
    dtype,
    preview_root: Path,
    previews: _PreviewOptions,
    *,
    max_side: int | None,
    seed: int,
    hf_cutoff_fraction: float,
    cancel_check: CancelCheck | None,
) -> _ReconstructionPass:
    """Encode/decode every image and score its high-frequency loss.

    A single image failing is not fatal — it is recorded in ``failures`` and left
    unassessed, so one unreadable file cannot cost the whole dataset its gate.
    """
    import torch
    from PIL import Image

    result = _ReconstructionPass()
    for path in images:
        check_cancel(cancel_check)
        try:
            recon = _encode_decode(vae, device, dtype, path, max_side=max_side, seed=seed)
            check_cancel(cancel_check)
            orig_arr = np.array(Image.open(path).convert("RGB").resize(
                (recon.shape[1], recon.shape[0]), Image.LANCZOS
            ))
            loss = _hf_loss(
                _to_lab_l(orig_arr),
                _to_lab_l(recon),
                cutoff_fraction=hf_cutoff_fraction,
            )
            if previews.writes_anything:
                result.review_artifacts[str(path)] = _save_review_artifacts(
                    path,
                    recon,
                    preview_root,
                    diff_amplification=previews.diff_amplification,
                    gaussian_blur_sigma=previews.gaussian_blur_sigma,
                    gaussian_blur_kernel=previews.gaussian_blur_kernel,
                    otsu_enabled=previews.otsu_enabled,
                    output_preview=previews.write_vae,
                    output_silhouette=previews.write_diff,
                    output_hard_silhouette=previews.write_hard,
                )
            result.hf_scores[str(path)] = loss
            result.reconstructions[str(path)] = recon
        except CancelledRun:
            raise
        except Exception as exc:
            reporter.warn(
                f"Reconstruction failed for {path.name}; keeping it unassessed: {exc}"
            )
            result.failures.append(
                {"stage": "reconstruct", "path": str(path), "error": str(exc)})
        finally:
            if device == "cuda":
                torch.cuda.empty_cache()
    return result


def _threshold_stats(
    hf_scores: dict[str, float],
    outlier_sigma: float,
) -> tuple[float | None, float | None, float | None]:
    """Mean/std/outlier threshold over the scored images, or ``None`` if none scored."""
    values = np.array(list(hf_scores.values()), dtype=np.float64)
    if not values.size:
        reporter.warn("No images were reconstructed successfully; no outliers were calculated.")
        return None, None, None

    mean = float(values.mean())
    std = float(values.std())
    threshold = mean + outlier_sigma * std
    reporter.info(f"HF-loss  mean={mean:.4f}  std={std:.4f}  threshold={threshold:.4f}")
    return mean, std, threshold


def _build_review_items(
    images: list[Path],
    recon: _ReconstructionPass,
    threshold: float | None,
    flagged_set: set[str],
    cancel_check: CancelCheck | None,
) -> list[dict]:
    """One review row per image that actually produced artifacts."""
    review_items: list[dict] = []
    for path in images:
        check_cancel(cancel_check)
        path_str = str(path)
        artifact = recon.review_artifacts.get(path_str)
        if artifact is None:
            continue
        review_items.append({
            "path": path_str,
            "name": path.name,
            "width": artifact.get("width"),
            "height": artifact.get("height"),
            "hf_loss": round(recon.hf_scores.get(path_str, 0.0), 5),
            "threshold": _rounded(threshold),
            "diff_threshold": artifact.get("diff_threshold"),
            "flagged": path_str in flagged_set,
            "initial_decision": "keep",
            "views": artifact.get("views", {}),
        })
    return review_items


def _collect_decisions(
    enabled: set[str],
    interaction: InteractionProvider | None,
    review_items: list[dict],
    flagged: list[str],
    recon: _ReconstructionPass,
    cancel_check: CancelCheck | None,
) -> dict[str, str]:
    """Keep/drop verdicts, from the UI gallery when there is one, else the CLI prompt.

    The CLI path only ever asks about flagged images; the gallery gets every
    reviewable item so a false negative can be caught by eye.
    """
    decisions: dict[str, str] = {}
    if "review_vae_artifacts" not in enabled:
        return decisions

    if interaction is not None and review_items:
        check_cancel(cancel_check)
        decisions.update(interaction.vae_review(review_items))
        check_cancel(cancel_check)
        return decisions

    # No gallery (headless, or nothing reviewable came back): fall back to the
    # per-image CLI prompt, which only ever asks about flagged images.
    for path_str in flagged:
        check_cancel(cancel_check)
        path = Path(path_str)
        reconstruction = recon.reconstructions.get(path_str)
        if reconstruction is not None:
            decision = _manual_flag_decision(path, reconstruction, recon.hf_scores[path_str])
        else:
            decision = "drop"
        decisions[path_str] = decision
        reporter.info(f"  {path.name} → {decision}")
    return decisions


def _decision_for(decisions: dict[str, str], path: Path) -> str:
    """The recorded verdict for ``path``, defaulting to ``keep``."""
    decision = decisions.get(str(path), decisions.get(str(path.resolve()), "keep"))
    return decision if decision in {"keep", "drop"} else "keep"


def _rounded(value: float | None) -> float | None:
    return round(float(value), 5) if value is not None else None


def _statistics(
    successful: int,
    failed: int,
    mean: float | None,
    std: float | None,
    threshold: float | None,
    outlier_sigma: float,
) -> dict:
    return {
        "successful": successful,
        "failed": failed,
        "mean": _rounded(mean),
        "std": _rounded(std),
        "threshold": _rounded(threshold),
        "outlier_sigma": outlier_sigma,
        "comparison": ">",
    }


def _substep_report(enabled: set[str]) -> dict:
    return {
        "reconstruct_images": {"enabled": "reconstruct_images" in enabled},
        "review_vae_artifacts": {"enabled": "review_vae_artifacts" in enabled},
        "apply_vae_decisions": {"enabled": "apply_vae_decisions" in enabled},
    }


def _materialize_with_captions(
    images: list[Path],
    survivors: list[Path],
    dataset_dir: Path,
    output_dir: Path,
) -> None:
    """Materialize selected images and keep matching caption sidecars paired."""
    survivor_paths = {path.resolve() for path in survivors}
    in_place = dataset_dir.resolve() == output_dir.resolve()
    img_utils.materialize(survivors, dataset_dir, output_dir)

    if in_place:
        for path in images:
            if path.resolve() not in survivor_paths:
                path.with_suffix(".txt").unlink(missing_ok=True)
        return

    for path in survivors:
        caption = path.with_suffix(".txt")
        if caption.is_file():
            destination = (output_dir / path.relative_to(dataset_dir)).with_suffix(".txt")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(caption, destination)


def _prune_unrequested_artifacts(
    artifacts: dict[str, dict],
    preview_root: Path,
    *,
    keep_vae: bool,
    keep_diff: bool,
    keep_hard: bool,
) -> None:
    """Remove UI-temporary views after review while preserving requested outputs."""
    keep_by_view = {"vae": keep_vae, "diff": keep_diff, "hard": keep_hard}
    resolved_root = preview_root.resolve()
    for artifact in artifacts.values():
        _drop_unkept_views(artifact.get("views", {}), keep_by_view, resolved_root)
    _remove_empty_dirs(preview_root)


def _drop_unkept_views(
    views: dict,
    keep_by_view: dict[str, bool],
    resolved_root: Path,
) -> None:
    """Delete (and unregister) the views this run was not asked to keep.

    The containment check is deliberate: ``views`` carries whatever path was
    recorded, and only files that actually live under the preview root are ours
    to unlink.
    """
    for view, keep in keep_by_view.items():
        if keep:
            continue
        raw_path = views.pop(view, None)
        if not raw_path:
            continue
        path = Path(raw_path)
        if path.resolve().is_relative_to(resolved_root):
            path.unlink(missing_ok=True)


def _remove_empty_dirs(preview_root: Path) -> None:
    """Prune directories left empty by pruning, deepest first, root included."""
    if not preview_root.exists():
        return
    for directory in sorted(
        (path for path in preview_root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        if not any(directory.iterdir()):
            directory.rmdir()
    if not any(preview_root.iterdir()):
        preview_root.rmdir()
