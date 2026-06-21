"""
Step 4 — VAE Reconstruction Gate

Encodes each image through the target model's VAE, decodes back, and measures
high-frequency loss via FFT power-spectrum comparison.  Outliers (> mean + 2σ)
are flagged for manual keep / drop / replace decision.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np

from ...networks.base import NetworkProfile
from ...utils import image as img_utils
from ...utils import report as rpt

from .hf_loss import _hf_loss
from .vae import _load_vae, _encode_decode, _to_lab_l
from .review import _manual_flag_decision


# ── Main ──────────────────────────────────────────────────────────────────────

def run(
    dataset_dir: Path,
    network: NetworkProfile,
    output_dir: Path | None = None,
    outlier_sigma: float = 2.0,
    report_path: Path | None = None,
) -> dict:
    rpt.step_header(4, "VAE Reconstruction Gate")

    output_dir = output_dir or dataset_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    images = img_utils.iter_images(dataset_dir)
    if not images:
        rpt.warn(f"No images in {dataset_dir}")
        return {}

    rpt.info(f"Loading VAE from {network.vae_model_id} …")
    try:
        vae, device, dtype = _load_vae(network.vae_model_id)
    except Exception as exc:
        rpt.error(f"VAE load failed: {exc}")
        rpt.warn("Skipping VAE gate — install diffusers and a supported model first.")
        return {"skipped": True, "reason": str(exc)}

    max_side = network.max_bucket_side
    rpt.info(f"Reconstructing {len(images)} images (device={device}, max_side={max_side}) …")

    hf_scores: dict[str, float] = {}
    reconstructions: dict[str, np.ndarray] = {}

    import torch
    from PIL import Image

    for path in images:
        try:
            recon = _encode_decode(vae, device, dtype, path, max_side=max_side)
            orig_arr = np.array(Image.open(path).convert("RGB").resize(
                (recon.shape[1], recon.shape[0]), Image.LANCZOS
            ))
            loss = _hf_loss(_to_lab_l(orig_arr), _to_lab_l(recon))
            hf_scores[str(path)] = loss
            reconstructions[str(path)] = recon
        except Exception as exc:
            rpt.error(f"Reconstruction failed for {path.name}: {exc}")
            hf_scores[str(path)] = 0.0
        finally:
            if device == "cuda":
                torch.cuda.empty_cache()

    values = np.array(list(hf_scores.values()))
    mean, std = values.mean(), values.std()
    threshold = mean + outlier_sigma * std
    rpt.info(f"HF-loss  mean={mean:.4f}  std={std:.4f}  threshold={threshold:.4f}")

    flagged = [p for p, s in hf_scores.items() if s >= threshold]
    rpt.warn(f"{len(flagged)} images flagged as high-frequency-loss outliers")

    decisions: dict[str, str] = {}
    for path_str in flagged:
        path = Path(path_str)
        recon = reconstructions.get(path_str)
        if recon is not None:
            decision = _manual_flag_decision(path, recon, hf_scores[path_str])
        else:
            decision = "drop"
        decisions[path_str] = decision
        rpt.info(f"  {path.name} → {decision}")

    survivors = [path for path in images if decisions.get(str(path), "keep") != "drop"]
    img_utils.materialize(survivors, dataset_dir, output_dir)

    report = {
        "hf_scores": {k: round(v, 5) for k, v in hf_scores.items()},
        "threshold": round(float(threshold), 5),
        "flagged": [
            {"path": p, "hf_loss": round(hf_scores[p], 5), "decision": decisions.get(p, "keep")}
            for p in flagged
        ],
        "needs_replacement": [p for p, d in decisions.items() if d == "replace"],
    }
    rpt.save_report(report, report_path or (output_dir / "step4_report.json"))
    return report
