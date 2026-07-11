from pathlib import Path
import hashlib
import re

import cv2
import numpy as np


def _review_artifact_dir(root: Path, original: Path) -> Path:
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", original.stem).strip("._")
    safe_stem = safe_stem or "image"
    suffix = hashlib.sha1(str(original.resolve()).encode("utf-8")).hexdigest()[:8]
    return root / f"{safe_stem}_{suffix}"


def _save_review_artifacts(
    original: Path,
    recon_arr: np.ndarray,
    preview_root: Path,
    *,
    diff_amplification: float = 4.0,
    gaussian_blur_sigma: float = 2.0,
    gaussian_blur_kernel: int = 21,
    otsu_enabled: bool = True,
    output_preview: bool = True,
    output_silhouette: bool = True,
    output_hard_silhouette: bool = True,
) -> dict:
    """Write review-only VAE artifacts and return their paths and metadata."""
    from PIL import Image

    recon_uint = np.clip(recon_arr, 0, 255).astype(np.uint8)
    height, width = recon_uint.shape[:2]
    with Image.open(original).convert("RGB") as img:
        orig_arr = np.array(img.resize((width, height), Image.LANCZOS))

    diff_arr, hard_arr, diff_threshold = _diff_views(
        orig_arr,
        recon_uint,
        diff_amplification=diff_amplification,
        gaussian_blur_sigma=gaussian_blur_sigma,
        gaussian_blur_kernel=gaussian_blur_kernel,
        otsu_enabled=otsu_enabled,
    )

    artifact_dir = _review_artifact_dir(preview_root, original)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    vae_path = artifact_dir / "vae.png"
    diff_path = artifact_dir / "diff.png"
    hard_path = artifact_dir / "hard.png"
    if output_preview:
        Image.fromarray(recon_uint).save(vae_path)
    if output_silhouette:
        Image.fromarray(diff_arr).save(diff_path)
    if output_hard_silhouette:
        Image.fromarray(hard_arr).save(hard_path)

    views = {"original": str(original)}
    if output_preview:
        views["vae"] = str(vae_path)
    if output_silhouette:
        views["diff"] = str(diff_path)
    if output_hard_silhouette:
        views["hard"] = str(hard_path)

    return {
        "width": width,
        "height": height,
        "diff_threshold": round(float(diff_threshold), 5),
        "views": views,
    }


def _diff_views(
    original_arr: np.ndarray,
    recon_arr: np.ndarray,
    *,
    diff_amplification: float,
    gaussian_blur_sigma: float,
    gaussian_blur_kernel: int,
    otsu_enabled: bool,
) -> tuple[np.ndarray, np.ndarray, float]:
    error = np.abs(
        original_arr.astype(np.float32) - recon_arr.astype(np.float32)
    ).mean(axis=2)
    error = np.clip(error, 0, 255).astype(np.uint8)

    blurred = error
    if gaussian_blur_sigma > 0 and gaussian_blur_kernel > 1:
        kernel = gaussian_blur_kernel if gaussian_blur_kernel % 2 == 1 else gaussian_blur_kernel + 1
        blurred = cv2.GaussianBlur(error, (kernel, kernel), gaussian_blur_sigma)

    if otsu_enabled and int(blurred.max()) > 0:
        threshold, _ = cv2.threshold(
            blurred,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
    else:
        threshold = float(blurred.mean() + blurred.std())

    mask = blurred > threshold
    amplified = blurred.astype(np.float32) * max(float(diff_amplification), 0.0)
    soft = np.where(mask, amplified, amplified * 0.25)
    soft_uint = np.clip(soft, 0, 255).astype(np.uint8)
    hard_uint = (mask.astype(np.uint8) * 255)
    return (
        np.repeat(soft_uint[:, :, None], 3, axis=2),
        np.repeat(hard_uint[:, :, None], 3, axis=2),
        float(threshold),
    )


def _review_artifact_decisions(items: list[dict]) -> dict[str, str]:
    decisions: dict[str, str] = {}
    for item in items:
        path = str(item.get("path") or "")
        if not path:
            continue
        initial = str(item.get("initial_decision") or "keep")
        print(f"\n  {item.get('name') or Path(path).name}  HF-loss={item.get('hf_loss', 'n/a')}")
        print(f"    original: {item.get('views', {}).get('original')}")
        print(f"    vae:      {item.get('views', {}).get('vae')}")
        print(f"    diff:     {item.get('views', {}).get('diff')}")
        print(f"    hard:     {item.get('views', {}).get('hard')}")
        ans = input(f"  [k]eep / [d]rop? [{initial[0]}] ").strip().lower()
        if not ans:
            decisions[path] = initial if initial in {"keep", "drop"} else "keep"
            continue
        decisions[path] = {"k": "keep", "d": "drop"}.get(ans[0], "keep")
    return decisions


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
            "The reconstruction is diagnostic only and never replaces the input.",
            title="Step 4 — VAE Gate",
            choices=["Keep", "Drop"],
        )
        return (choice or "keep").lower()
    except ImportError:
        print(f"\n  {original.name}  HF-loss={hf_score:.4f}")
        ans = input("  [k]eep / [d]rop? ").strip().lower()
        return {"k": "keep", "d": "drop"}.get(ans[0] if ans else "k", "keep")
