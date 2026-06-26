"""Occlusion filter via CLIP zero-shot for Step 2 curation."""
from __future__ import annotations
from pathlib import Path

from ...cancellation import CancelCheck, check_cancel

OCCLUSION_THRESHOLD = 0.35   # below this CLIP score → flag as occluded


def _occlusion_scores(
    paths: list[Path],
    clip_model_id: str | None = None,
    cancel_check: CancelCheck | None = None,
) -> dict[Path, float]:
    import torch
    from PIL import Image
    from ...embedding import catalog
    from .clip_model import load_clip

    clip = load_clip(clip_model_id or catalog.DEFAULT_CLIP_ID)

    prompts = [
        "a photo where the main subject is fully visible and unoccluded",
        "a photo where the main subject is partially hidden or occluded",
    ]
    text_tokens = clip.tokenizer(prompts).to(clip.device)
    scores = {}
    with torch.no_grad():
        text_feat = clip.model.encode_text(text_tokens)
        text_feat = text_feat / text_feat.norm(dim=-1, keepdim=True)
        logit_scale = clip.model.logit_scale.exp()
        for p in paths:
            check_cancel(cancel_check)
            image = Image.open(p).convert("RGB")
            img = clip.preprocess(image).unsqueeze(0).to(clip.device)
            img_feat = clip.model.encode_image(img)
            img_feat = img_feat / img_feat.norm(dim=-1, keepdim=True)
            logits = (logit_scale * img_feat @ text_feat.T)[0]
            prob_clear = float(logits.softmax(dim=0)[0].item())
            scores[p] = prob_clear
    return scores
