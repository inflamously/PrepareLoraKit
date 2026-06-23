"""Occlusion filter via CLIP zero-shot for Step 2 curation."""
from __future__ import annotations
from pathlib import Path

from ...cancellation import CancelCheck, check_cancel

OCCLUSION_THRESHOLD = 0.35   # below this CLIP score → flag as occluded


def _occlusion_scores(paths: list[Path], cancel_check: CancelCheck | None = None) -> dict[Path, float]:
    import torch
    from PIL import Image
    from .clip_model import load_clip

    model, processor = load_clip()

    prompts = [
        "a photo where the main subject is fully visible and unoccluded",
        "a photo where the main subject is partially hidden or occluded",
    ]
    scores = {}
    for p in paths:
        check_cancel(cancel_check)
        image = Image.open(p).convert("RGB")
        inputs = processor(text=prompts, images=image, return_tensors="pt", padding=True)
        with torch.no_grad():
            logits = model(**inputs).logits_per_image[0]
            prob_clear = float(logits.softmax(dim=0)[0].item())
        scores[p] = prob_clear
    return scores
