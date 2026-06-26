"""Image-embedding loaders and dispatch for the Curate step.

All heavy imports (``torch``, ``open_clip``, ``transformers``) are lazy so this
module — and anything importing the catalog through it — stays cheap to import.

Two entry points:
  * :func:`embed_images` — coverage embeddings for any catalog family.
  * :func:`load_clip` — an open_clip model + tokenizer for the occlusion filter,
    which needs text<->image scoring (CLIP only).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..cancellation import CancelCheck, check_cancel
from . import catalog


@dataclass
class LoadedClip:
    """An open_clip model bundle for zero-shot text<->image scoring."""

    model: object
    preprocess: object
    tokenizer: object
    device: str


def _resolve(model_id: str) -> catalog.EmbeddingModel:
    """Catalog entry for ``model_id``, inferring a sensible spec for custom ids."""
    entry = catalog.get(model_id)
    if entry is not None:
        return entry
    # Custom / unknown id: infer the family so custom dropdown entries still work.
    low = model_id.lower()
    if "dinov2" in low:
        return catalog.EmbeddingModel(model_id, model_id, "dinov2", 0, 0.0, hf_repo=model_id)
    if "qwen" in low:
        return catalog.EmbeddingModel(model_id, model_id, "qwen", 0, 0.0, hf_repo=model_id)
    if "/" in model_id:
        # Generic HF vision model — treat like DINOv2 (CLS/pooled embedding).
        return catalog.EmbeddingModel(model_id, model_id, "dinov2", 0, 0.0, hf_repo=model_id)
    # Bare name → assume an open_clip architecture.
    return catalog.EmbeddingModel(model_id, model_id, "clip", 0, 0.0)


def _device(torch) -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def _load_open_clip(spec: catalog.EmbeddingModel):
    import torch
    import open_clip

    device = _device(torch)
    model, _, preprocess = open_clip.create_model_and_transforms(
        spec.arch, pretrained=spec.open_clip_pretrained
    )
    model.eval().to(device)
    tokenizer = open_clip.get_tokenizer(spec.arch)
    return model, preprocess, tokenizer, device


def load_clip(model_id: str = catalog.DEFAULT_CLIP_ID) -> LoadedClip:
    """Load an open_clip model bundle for the occlusion filter.

    Non-CLIP ids are coerced to the default CLIP model, since occlusion needs a
    text encoder that DINOv2/Qwen-embedding models don't provide.
    """
    spec = _resolve(model_id)
    if spec.family != "clip":
        spec = _resolve(catalog.DEFAULT_CLIP_ID)
    model, preprocess, tokenizer, device = _load_open_clip(spec)
    return LoadedClip(model=model, preprocess=preprocess, tokenizer=tokenizer, device=device)


def _embed_clip(spec, paths: list[Path], cancel_check):
    import numpy as np
    import torch
    from PIL import Image

    model, preprocess, _tokenizer, device = _load_open_clip(spec)
    rows = []
    with torch.no_grad():
        for p in paths:
            check_cancel(cancel_check)
            img = preprocess(Image.open(p).convert("RGB")).unsqueeze(0).to(device)
            feat = model.encode_image(img)
            feat = feat / feat.norm(dim=-1, keepdim=True)
            rows.append(feat[0].cpu().numpy().reshape(-1))
    return np.stack(rows)


def _embed_dinov2(spec, paths: list[Path], cancel_check):
    import numpy as np
    import torch
    from PIL import Image
    from transformers import AutoImageProcessor, AutoModel

    device = _device(torch)
    processor = AutoImageProcessor.from_pretrained(spec.hf_repo)
    model = AutoModel.from_pretrained(spec.hf_repo).eval().to(device)
    rows = []
    with torch.no_grad():
        for p in paths:
            check_cancel(cancel_check)
            image = Image.open(p).convert("RGB")
            inputs = processor(images=image, return_tensors="pt").to(device)
            outputs = model(**inputs)
            # pooler_output is the CLS-derived global descriptor; fall back to the
            # CLS token of the last hidden state for models without a pooler.
            feat = getattr(outputs, "pooler_output", None)
            if feat is None:
                feat = outputs.last_hidden_state[:, 0]
            rows.append(feat[0].cpu().numpy().reshape(-1))
    return np.stack(rows)


def _embed_qwen(spec, paths: list[Path], cancel_check):
    import numpy as np
    import torch
    from PIL import Image
    from transformers import AutoModel, AutoProcessor

    device = _device(torch)
    processor = AutoProcessor.from_pretrained(spec.hf_repo, trust_remote_code=True)
    model = AutoModel.from_pretrained(spec.hf_repo, trust_remote_code=True).eval().to(device)
    rows = []
    with torch.no_grad():
        for p in paths:
            check_cancel(cancel_check)
            image = Image.open(p).convert("RGB")
            inputs = processor(images=image, return_tensors="pt").to(device)
            outputs = model(**inputs)
            feat = getattr(outputs, "pooler_output", None)
            if feat is None:
                hidden = outputs.last_hidden_state
                feat = hidden.mean(dim=1)  # mean-pool patch/token embeddings
            rows.append(feat[0].cpu().numpy().reshape(-1))
    return np.stack(rows)


def embed_images(model_id: str, paths: list[Path], cancel_check: CancelCheck | None = None):
    """Return an ``(N, D)`` array of L2-comparable image embeddings.

    Dispatches by catalog family; ``model_id`` may be an ``auto``-resolved id, a
    catalog id, or a custom HF repo / open_clip arch name.
    """
    spec = _resolve(model_id)
    if spec.family == "clip":
        return _embed_clip(spec, paths, cancel_check)
    if spec.family == "dinov2":
        return _embed_dinov2(spec, paths, cancel_check)
    if spec.family == "qwen":
        return _embed_qwen(spec, paths, cancel_check)
    raise ValueError(f"Unsupported embedding family for model id: {model_id!r}")
