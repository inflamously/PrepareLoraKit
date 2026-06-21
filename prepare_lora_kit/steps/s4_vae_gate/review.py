from pathlib import Path
import numpy as np


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
