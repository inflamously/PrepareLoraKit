import numpy as np

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
