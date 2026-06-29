from pathlib import Path
import numpy as np

# Bare-checkpoint suffixes routed to ``from_single_file`` instead of a diffusers repo.
_SINGLE_FILE_SUFFIXES = (".safetensors", ".ckpt", ".pt", ".bin")


# ── VAE encode-decode ─────────────────────────────────────────────────────────

def _instantiate_vae(model_id: str, AutoencoderKL, config_id: str | None = None):
    """Build an ``AutoencoderKL`` from one of three ``vae_model_id`` forms:

    - ``repo_id::path/in/repo.safetensors`` → download just that file, then single-file load.
    - a path/URL ending in a checkpoint suffix → single-file load.
    - anything else (a diffusers repo id or local dir) → ``from_pretrained(subfolder="vae")``.

    ``config_id`` (optional) points the single-file loader at a base repo's ``vae/`` config
    for checkpoints diffusers cannot auto-configure from their state-dict keys.
    """
    if "::" in model_id:
        repo_id, filename = model_id.split("::", 1)
        from huggingface_hub import hf_hub_download

        local = hf_hub_download(repo_id, filename)
        return _from_single_file(AutoencoderKL, local, config_id)
    if model_id.lower().endswith(_SINGLE_FILE_SUFFIXES):
        return _from_single_file(AutoencoderKL, model_id, config_id)
    return AutoencoderKL.from_pretrained(model_id, subfolder="vae")


def _from_single_file(AutoencoderKL, path: str, config_id: str | None = None):
    if config_id:
        return AutoencoderKL.from_single_file(path, config=config_id, subfolder="vae")
    return AutoencoderKL.from_single_file(path)


def _load_vae(model_id: str, config_id: str | None = None):
    import torch
    from diffusers import AutoencoderKL

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    vae = _instantiate_vae(model_id, AutoencoderKL, config_id).to(device, dtype=dtype)
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
