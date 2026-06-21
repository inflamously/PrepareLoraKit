"""Shared CLIP model loader for Step 2 curation."""
from __future__ import annotations


def load_clip(model_id: str = "openai/clip-vit-base-patch32"):
    from transformers import CLIPModel, CLIPProcessor

    model = CLIPModel.from_pretrained(model_id)
    processor = CLIPProcessor.from_pretrained(model_id)
    model.eval()
    return model, processor
