"""CLIP coverage visualisation for Step 2 curation."""
from __future__ import annotations
from pathlib import Path

from ...cancellation import CancelCheck, check_cancel
from ...utils import report as rpt


def _clip_embeddings(paths: list[Path], cancel_check: CancelCheck | None = None) -> "np.ndarray":
    import torch
    import numpy as np
    from PIL import Image
    from .clip_model import load_clip

    model, processor = load_clip()

    embeddings = []
    for p in paths:
        check_cancel(cancel_check)
        image = Image.open(p).convert("RGB")
        inputs = processor(images=image, return_tensors="pt")
        with torch.no_grad():
            feat = model.get_image_features(**inputs)
        # Flatten to 1D so the stacked array is 2D (N, D) for PCA/UMAP,
        # regardless of whether the model returns pooled (D,) or spatial (C,H,W) features.
        embeddings.append(feat[0].cpu().numpy().reshape(-1))
    check_cancel(cancel_check)
    return np.stack(embeddings)


def _save_umap(embeddings, paths: list[Path], out_path: Path) -> dict:
    import warnings

    import matplotlib.pyplot as plt
    from sklearn.decomposition import PCA
    from umap import UMAP

    pca_components = min(50, embeddings.shape[0] - 1, embeddings.shape[1])
    reduced = PCA(n_components=pca_components).fit_transform(embeddings)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"n_jobs value .* overridden to 1 by setting random_state.*",
            category=UserWarning,
            module=r"umap\.umap_",
        )
        reducer = UMAP(n_components=2, random_state=42)
        coords = reducer.fit_transform(reduced)

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.scatter(coords[:, 0], coords[:, 1], alpha=0.7, s=60)
    for i, p in enumerate(paths):
        ax.annotate(p.name[:20], (coords[i, 0], coords[i, 1]), fontsize=6, alpha=0.6)
    ax.set_title("Dataset Coverage — CLIP UMAP")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    rpt.ok(f"Coverage UMAP saved → {out_path}")
    return {
        "method": "umap",
        "embedding": "clip",
        "preprocess": "pca",
        "pca_components": int(pca_components),
    }


def _save_pca(embeddings, paths: list[Path], out_path: Path) -> dict:
    import matplotlib.pyplot as plt
    from sklearn.decomposition import PCA

    coords = PCA(n_components=2).fit_transform(embeddings)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(coords[:, 0], coords[:, 1], alpha=0.8, s=60)
    for i, p in enumerate(paths):
        ax.annotate(p.name[:20], (coords[i, 0], coords[i, 1]), fontsize=6, alpha=0.6)
    ax.set_title("Dataset Coverage — CLIP PCA")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    rpt.ok(f"Coverage PCA saved → {out_path}")
    return {
        "method": "pca",
        "embedding": "clip",
        "pca_components": 2,
    }
