"""
Step 4 — VAE Reconstruction Gate

Encodes each image through the target model's VAE, decodes back, and measures
high-frequency loss via FFT power-spectrum comparison.  Outliers (> mean + 2σ)
are flagged for manual keep / drop / replace decision.
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

    images = img_utils.iter_images(dataset_dir)
    if not images:
        reporter.warn(f"No images in {dataset_dir}")
        return {}

    if "reconstruct_images" not in enabled:
        reporter.info("VAE reconstruction substep disabled; passing through originals.")
        img_utils.materialize(images, dataset_dir, output_dir)
        report_data = {
            "skipped": True,
            "reason": "reconstruct_images disabled",
            "hf_scores": {},
            "flagged": [],
            "review_items": [],
            "needs_replacement": [],
            "substeps": {
                "reconstruct_images": {"enabled": False},
                "review_vae_artifacts": {"enabled": "review_vae_artifacts" in enabled},
                "apply_vae_decisions": {"enabled": "apply_vae_decisions" in enabled},
            },
        }
        reporter.save_report(report_data, report_path or (output_dir / "step4_report.json"))
        return report_data

    reporter.info(f"Loading VAE from {vae_model_id} …")
    check_cancel(cancel_check)
    try:
        vae, device, dtype = _load_vae(vae_model_id, vae_config_id)
    except Exception as exc:
        reporter.error(f"VAE load failed: {exc}")
        reporter.warn("Skipping VAE gate — install diffusers and a supported model first.")
        return {"skipped": True, "reason": str(exc)}

    reporter.info(f"Reconstructing {len(images)} images (device={device}, max_side={max_side}) …")

    hf_scores: dict[str, float] = {}
    reconstructions: dict[str, np.ndarray] = {}
    review_artifacts: dict[str, dict] = {}
    preview_root = (
        (report_path.parent if report_path else output_dir) / "VaeGateStep_previews"
    )
    should_write_previews = (
        output_previews
        or output_silhouettes
        or output_hard_silhouettes
        or interaction is not None
    )
    if should_write_previews and preview_root.exists():
        shutil.rmtree(preview_root)

    import torch
    from PIL import Image

    for path in images:
        check_cancel(cancel_check)
        try:
            recon = _encode_decode(vae, device, dtype, path, max_side=max_side)
            check_cancel(cancel_check)
            orig_arr = np.array(Image.open(path).convert("RGB").resize(
                (recon.shape[1], recon.shape[0]), Image.LANCZOS
            ))
            loss = _hf_loss(_to_lab_l(orig_arr), _to_lab_l(recon))
            hf_scores[str(path)] = loss
            reconstructions[str(path)] = recon
            if should_write_previews:
                review_artifacts[str(path)] = _save_review_artifacts(
                    path,
                    recon,
                    preview_root,
                    diff_amplification=diff_amplification,
                    gaussian_blur_sigma=gaussian_blur_sigma,
                    gaussian_blur_kernel=gaussian_blur_kernel,
                    otsu_enabled=otsu_enabled,
                )
        except CancelledRun:
            raise
        except Exception as exc:
            reporter.error(f"Reconstruction failed for {path.name}: {exc}")
            hf_scores[str(path)] = 0.0
        finally:
            if device == "cuda":
                torch.cuda.empty_cache()

    values = np.array(list(hf_scores.values()))
    mean, std = values.mean(), values.std()
    threshold = mean + outlier_sigma * std
    reporter.info(f"HF-loss  mean={mean:.4f}  std={std:.4f}  threshold={threshold:.4f}")

    flagged = [p for p, s in hf_scores.items() if s >= threshold]
    flagged_set = set(flagged)
    reporter.warn(f"{len(flagged)} images flagged as high-frequency-loss outliers")

    decisions: dict[str, str] = {}
    review_items: list[dict] = []
    for path in images:
        check_cancel(cancel_check)
        path_str = str(path)
        artifact = review_artifacts.get(path_str)
        if artifact is None and path_str in flagged_set and path_str not in reconstructions:
            decisions[path_str] = "drop"
            continue
        if artifact is None:
            continue
        item = {
            "path": path_str,
            "name": path.name,
            "width": artifact.get("width"),
            "height": artifact.get("height"),
            "hf_loss": round(hf_scores.get(path_str, 0.0), 5),
            "threshold": round(float(threshold), 5),
            "diff_threshold": artifact.get("diff_threshold"),
            "flagged": path_str in flagged_set,
            "initial_decision": "replace" if path_str in flagged_set else "keep",
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

    def decision_for(path: Path) -> str:
        default = "replace" if str(path) in flagged_set else "keep"
        return decisions.get(str(path), decisions.get(str(path.resolve()), default))

    survivors = (
        [path for path in images if decision_for(path) != "drop"]
        if "apply_vae_decisions" in enabled
        else list(images)
    )
    check_cancel(cancel_check)
    img_utils.materialize(survivors, dataset_dir, output_dir)

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
        "threshold": round(float(threshold), 5),
        "flagged": [
            {"path": p, "hf_loss": round(hf_scores[p], 5), "decision": decision_for(Path(p))}
            for p in flagged
        ],
        "review_items": reviewed,
        "needs_replacement": [
            str(path)
            for path in images
            if decision_for(path) == "replace"
        ],
        "substeps": {
            "reconstruct_images": {"enabled": "reconstruct_images" in enabled},
            "review_vae_artifacts": {"enabled": "review_vae_artifacts" in enabled},
            "apply_vae_decisions": {"enabled": "apply_vae_decisions" in enabled},
        },
    }
    check_cancel(cancel_check)
    reporter.save_report(report_data, report_path or (output_dir / "step4_report.json"))
    return report_data
