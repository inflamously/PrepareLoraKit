"""
Step 4 — VAE Reconstruction Gate

Encodes each image through the target model's VAE, decodes back, and measures
high-frequency loss via FFT power-spectrum comparison.  Outliers (> mean + 2σ)
are flagged for manual keep / drop / replace decision.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np

from ..networks.base import NetworkProfile
from ..utils import image as img_utils
from ..utils import report as rpt

HF_CUTOFF_FRACTION = 0.25   # fraction of image that counts as "high frequency"


# ── FFT-based HF loss ─────────────────────────────────────────────────────────

def _hf_loss(original: np.ndarray, reconstructed: np.ndarray) -> float:
    """
    Compare high-frequency power between original and reconstruction.
    Both arrays are HxW float32 (L channel of LAB).
    Returns relative HF power lost; higher = more detail destroyed.
    """
    def _hf_power(img: np.ndarray) -> float:
        f = np.fft.fft2(img)
        fshift = np.fft.fftshift(f)
        magnitude = np.abs(fshift)
        h, w = img.shape
        cy, cx = h // 2, w // 2
        cut_h = int(h * HF_CUTOFF_FRACTION)
        cut_w = int(w * HF_CUTOFF_FRACTION)
        # Zero the low-freq centre
        mask = np.ones_like(magnitude)
        mask[cy - cut_h: cy + cut_h, cx - cut_w: cx + cut_w] = 0
        return float((magnitude * mask).mean())

    orig_hf = _hf_power(original)
    recon_hf = _hf_power(reconstructed)
    if orig_hf < 1e-6:
        return 0.0
    return float(max(0.0, (orig_hf - recon_hf) / orig_hf))


# ── VAE encode-decode ─────────────────────────────────────────────────────────

def _load_vae(model_id: str):
    import torch
    from diffusers import AutoencoderKL

    device = "cuda" if __import__("torch").cuda.is_available() else "cpu"
    dtype = __import__("torch").float16 if device == "cuda" else __import__("torch").float32
    vae = AutoencoderKL.from_pretrained(model_id, subfolder="vae").to(device, dtype=dtype)
    vae.eval()
    return vae, device, dtype


def _encode_decode(vae, device, dtype, path: Path) -> np.ndarray:
    import torch
    from PIL import Image
    import torchvision.transforms as T

    img = Image.open(path).convert("RGB")
    # Resize to nearest multiple of 8 (VAE requirement)
    w, h = img.size
    w = (w // 8) * 8
    h = (h // 8) * 8
    img = img.resize((w, h), Image.LANCZOS)

    tensor = T.ToTensor()(img).unsqueeze(0).to(device, dtype=dtype) * 2 - 1  # [-1, 1]
    with torch.no_grad():
        latent = vae.encode(tensor).latent_dist.sample(
            generator=torch.Generator(device=device).manual_seed(42)
        )
        recon = vae.decode(latent).sample

    recon_img = ((recon.squeeze(0).cpu().float().clamp(-1, 1) + 1) / 2 * 255).byte()
    return recon_img.permute(1, 2, 0).numpy()


def _to_lab_l(img_np: np.ndarray) -> np.ndarray:
    import cv2
    lab = cv2.cvtColor(img_np.astype(np.uint8), cv2.COLOR_RGB2LAB)
    return lab[:, :, 0].astype(np.float32)


# ── Manual decision UI ────────────────────────────────────────────────────────

def _manual_flag_decision(original: Path, recon_arr: np.ndarray, hf_score: float) -> str:
    from PIL import Image

    orig_pil = Image.open(original).convert("RGB")
    recon_pil = Image.fromarray(recon_arr.astype(np.uint8))

    # Side-by-side
    w = orig_pil.width + recon_pil.width + 10
    h = max(orig_pil.height, recon_pil.height)
    combined = Image.new("RGB", (w, h), (20, 20, 20))
    combined.paste(orig_pil, (0, 0))
    combined.paste(recon_pil, (orig_pil.width + 10, 0))
    combined.show()

    try:
        import easygui
        choice = easygui.buttonbox(
            f"File: {original.name}\nHF-loss score: {hf_score:.4f}\n\n"
            "Left = original | Right = VAE reconstruction\n\n"
            "• Keep: silhouette / outline still carries the concept\n"
            "• Drop: concept lives in the lost detail\n"
            "• Replace: add to needs-replacement list",
            title="Step 4 — VAE Gate",
            choices=["Keep", "Drop", "Replace"],
        )
        return (choice or "keep").lower()
    except ImportError:
        print(f"\n  {original.name}  HF-loss={hf_score:.4f}")
        ans = input("  [k]eep / [d]rop / [r]eplace? ").strip().lower()
        return {"k": "keep", "d": "drop", "r": "replace"}.get(ans[0] if ans else "k", "keep")


# ── Main ──────────────────────────────────────────────────────────────────────

def run(
    dataset_dir: Path,
    network: NetworkProfile,
    output_dir: Path | None = None,
    outlier_sigma: float = 2.0,
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

    rpt.info(f"Reconstructing {len(images)} images (device={device}) …")

    hf_scores: dict[str, float] = {}
    reconstructions: dict[str, np.ndarray] = {}

    for path in images:
        try:
            recon = _encode_decode(vae, device, dtype, path)
            orig_arr = np.array(__import__("PIL").Image.open(path).convert("RGB").resize(
                (recon.shape[1], recon.shape[0]), __import__("PIL").Image.LANCZOS
            ))
            loss = _hf_loss(_to_lab_l(orig_arr), _to_lab_l(recon))
            hf_scores[str(path)] = loss
            reconstructions[str(path)] = recon
        except Exception as exc:
            rpt.error(f"Reconstruction failed for {path.name}: {exc}")
            hf_scores[str(path)] = 0.0

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

    report = {
        "hf_scores": {k: round(v, 5) for k, v in hf_scores.items()},
        "threshold": round(float(threshold), 5),
        "flagged": [
            {"path": p, "hf_loss": round(hf_scores[p], 5), "decision": decisions.get(p, "keep")}
            for p in flagged
        ],
        "needs_replacement": [p for p, d in decisions.items() if d == "replace"],
    }
    rpt.save_report(report, output_dir / "step4_report.json")
    return report
