from pathlib import Path
import numpy as np


# ── VAE encode-decode ─────────────────────────────────────────────────────────

def _load_vae(model_id: str):
    import torch
    from diffusers import AutoencoderKL

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    vae = AutoencoderKL.from_pretrained(model_id, subfolder="vae").to(device, dtype=dtype)
    vae.eval()
    vae.enable_tiling()   # constant VRAM regardless of image size
    vae.enable_slicing()  # reduces peak VRAM for batch dim
    return vae, device, dtype


def _encode_decode(vae, device, dtype, path: Path, max_side: int = 2048) -> np.ndarray:
    import torch
    from PIL import Image
    import torchvision.transforms as T

    img = Image.open(path).convert("RGB")
    w, h = img.size
    # Cap longest side to max_side before encoding
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        w, h = int(w * scale), int(h * scale)
    # Snap to multiple of 8 (VAE requirement)
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
