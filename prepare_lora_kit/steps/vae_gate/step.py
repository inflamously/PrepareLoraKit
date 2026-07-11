"""
Step 4 — VAE Reconstruction Gate

Encodes each image through the target model's VAE, decodes back, and measures
high-frequency loss via FFT spectrum comparison. Outliers (> mean + 2σ) are
flagged for a manual keep / drop decision. Reconstructions are diagnostics only.
"""
from __future__ import annotations
from pathlib import Path
import shutil
import numpy as np

from prepare_lora_kit.cancellation import CancelCheck, CancelledRun, check_cancel
from prepare_lora_kit.providers.interaction import InteractionProvider
from prepare_lora_kit.utils import image as img_utils
from prepare_lora_kit.report import reporter


from prepare_lora_kit.steps.vae_gate.hf_loss import _hf_loss
from prepare_lora_kit.steps.vae_gate.vae import _load_vae, _encode_decode, _to_lab_l
from prepare_lora_kit.steps.vae_gate.review import _manual_flag_decision, _save_review_artifacts

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
        report_data = {
            "skipped": True,
            "reason": "no images",
            "hf_scores": {},
            "threshold": None,
            "statistics": _statistics(0, 0, None, None, None, outlier_sigma),
            "flagged": [],
            "failures": [],
            "review_items": [],
            "substeps": _substep_report(enabled),
        }
        reporter.save_report(report_data, target_report)
        return report_data

    if "reconstruct_images" not in enabled:
        reporter.info("VAE reconstruction substep disabled; passing through originals.")
        _materialize_with_captions(images, images, dataset_dir, output_dir)
        report_data = {
            "skipped": True,
            "reason": "reconstruct_images disabled",
            "hf_scores": {},
            "threshold": None,
            "statistics": _statistics(0, 0, None, None, None, outlier_sigma),
            "flagged": [],
            "failures": [],
            "review_items": [],
            "substeps": _substep_report(enabled),
        }
        reporter.save_report(report_data, target_report)
        return report_data

    reporter.info(f"Loading VAE from {vae_model_id} …")
    check_cancel(cancel_check)
    try:
        vae, device, dtype = _load_vae(vae_model_id, vae_config_id)
    except Exception as exc:
        reporter.error(f"VAE load failed: {exc}")
        reporter.warn("VAE gate could not assess the dataset; all inputs remain unchanged.")
        report_data = {
            "skipped": True,
            "reason": str(exc),
            "hf_scores": {},
            "threshold": None,
            "statistics": _statistics(0, len(images), None, None, None, outlier_sigma),
            "flagged": [],
            "failures": [{"stage": "load", "path": None, "error": str(exc)}],
            "review_items": [],
            "substeps": _substep_report(enabled),
        }
        reporter.save_report(report_data, target_report)
        return report_data

    reporter.info(f"Reconstructing {len(images)} images (device={device}, max_side={max_side}) …")

    hf_scores: dict[str, float] = {}
    reconstructions: dict[str, np.ndarray] = {}
    review_artifacts: dict[str, dict] = {}
    failures: list[dict] = []
    interactive_review = "review_vae_artifacts" in enabled and interaction is not None
    write_vae = output_previews or interactive_review
    write_diff = output_silhouettes or interactive_review
    write_hard = output_hard_silhouettes or interactive_review
    should_write_previews = write_vae or write_diff or write_hard

    import torch
    from PIL import Image

    for path in images:
        check_cancel(cancel_check)
        try:
            recon = _encode_decode(
                vae, device, dtype, path, max_side=max_side, seed=seed
            )
            check_cancel(cancel_check)
            orig_arr = np.array(Image.open(path).convert("RGB").resize(
                (recon.shape[1], recon.shape[0]), Image.LANCZOS
            ))
            loss = _hf_loss(
                _to_lab_l(orig_arr),
                _to_lab_l(recon),
                cutoff_fraction=hf_cutoff_fraction,
            )
            if should_write_previews:
                review_artifacts[str(path)] = _save_review_artifacts(
                    path,
                    recon,
                    preview_root,
                    diff_amplification=diff_amplification,
                    gaussian_blur_sigma=gaussian_blur_sigma,
                    gaussian_blur_kernel=gaussian_blur_kernel,
                    otsu_enabled=otsu_enabled,
                    output_preview=write_vae,
                    output_silhouette=write_diff,
                    output_hard_silhouette=write_hard,
                )
            hf_scores[str(path)] = loss
            reconstructions[str(path)] = recon
        except CancelledRun:
            raise
        except Exception as exc:
            reporter.warn(
                f"Reconstruction failed for {path.name}; keeping it unassessed: {exc}"
            )
            failures.append({"stage": "reconstruct", "path": str(path), "error": str(exc)})
        finally:
            if device == "cuda":
                torch.cuda.empty_cache()

    values = np.array(list(hf_scores.values()), dtype=np.float64)
    if values.size:
        mean = float(values.mean())
        std = float(values.std())
        threshold = mean + outlier_sigma * std
        reporter.info(f"HF-loss  mean={mean:.4f}  std={std:.4f}  threshold={threshold:.4f}")
    else:
        mean = std = threshold = None
        reporter.warn("No images were reconstructed successfully; no outliers were calculated.")

    flagged = [
        p for p, score in hf_scores.items()
        if threshold is not None and score > threshold
    ]
    flagged_set = set(flagged)
    reporter.warn(f"{len(flagged)} images flagged as high-frequency-loss outliers")

    decisions: dict[str, str] = {}
    review_items: list[dict] = []
    for path in images:
        check_cancel(cancel_check)
        path_str = str(path)
        artifact = review_artifacts.get(path_str)
        if artifact is None:
            continue
        item = {
            "path": path_str,
            "name": path.name,
            "width": artifact.get("width"),
            "height": artifact.get("height"),
            "hf_loss": round(hf_scores.get(path_str, 0.0), 5),
            "threshold": _rounded(threshold),
            "diff_threshold": artifact.get("diff_threshold"),
            "flagged": path_str in flagged_set,
            "initial_decision": "keep",
            "views": artifact.get("views", {}),
        }
        review_items.append(item)

    if "review_vae_artifacts" in enabled and interaction is not None and review_items:
        check_cancel(cancel_check)
        decisions.update(interaction.vae_review(review_items))
        check_cancel(cancel_check)
    elif "review_vae_artifacts" in enabled:
        for path_str in flagged:
            check_cancel(cancel_check)
            path = Path(path_str)
            recon = reconstructions.get(path_str)
            if recon is not None:
                decision = _manual_flag_decision(path, recon, hf_scores[path_str])
            else:
                decision = "drop"
            decisions[path_str] = decision
            reporter.info(f"  {path.name} → {decision}")

    if interactive_review:
        _prune_unrequested_artifacts(
            review_artifacts,
            preview_root,
            keep_vae=output_previews,
            keep_diff=output_silhouettes,
            keep_hard=output_hard_silhouettes,
        )

    def decision_for(path: Path) -> str:
        decision = decisions.get(str(path), decisions.get(str(path.resolve()), "keep"))
        return decision if decision in {"keep", "drop"} else "keep"

    survivors = (
        [path for path in images if decision_for(path) != "drop"]
        if "apply_vae_decisions" in enabled
        else list(images)
    )
    check_cancel(cancel_check)
    _materialize_with_captions(images, survivors, dataset_dir, output_dir)

    reviewed = []
    for item in review_items:
        check_cancel(cancel_check)
        path = Path(str(item["path"]))
        decision = decision_for(path)
        reviewed.append({**item, "decision": decision})
        if decision != "keep":
            reporter.info(f"  {path.name} → {decision}")

    report_data = {
        "hf_scores": {k: round(v, 5) for k, v in hf_scores.items()},
        "threshold": _rounded(threshold),
        "statistics": _statistics(
            len(hf_scores), len(failures), mean, std, threshold, outlier_sigma
        ),
        "flagged": [
            {"path": p, "hf_loss": round(hf_scores[p], 5), "decision": decision_for(Path(p))}
            for p in flagged
        ],
        "failures": failures,
        "review_items": reviewed,
        "substeps": _substep_report(enabled),
    }
    check_cancel(cancel_check)
    reporter.save_report(report_data, target_report)
    return report_data


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
        views = artifact.get("views", {})
        for view, keep in keep_by_view.items():
            if keep:
                continue
            raw_path = views.pop(view, None)
            if not raw_path:
                continue
            path = Path(raw_path)
            if path.resolve().is_relative_to(resolved_root):
                path.unlink(missing_ok=True)

    if preview_root.exists() and not any(preview_root.rglob("*")):
        preview_root.rmdir()
    elif preview_root.exists():
        for directory in sorted(
            (path for path in preview_root.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            if not any(directory.iterdir()):
                directory.rmdir()
        if not any(preview_root.iterdir()):
            preview_root.rmdir()
