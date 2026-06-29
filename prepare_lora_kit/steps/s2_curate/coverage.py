"""CLIP coverage visualisation for Step 2 curation."""
from __future__ import annotations
from collections import Counter
from pathlib import Path

from ...cancellation import CancelCheck, check_cancel
from ...utils import report as rpt

_LABEL_MAX = 24


def _point_labels(paths: list[Path]) -> list[str]:
    """Per-point scatter labels, prefixing the parent dir only when a bare
    filename is shared by more than one path so collisions stay distinguishable."""
    name_counts = Counter(p.name for p in paths)
    labels = []
    for p in paths:
        label = f"{p.parent.name}/{p.name}" if name_counts[p.name] > 1 else p.name
        if len(label) > _LABEL_MAX:
            label = "…" + label[-(_LABEL_MAX - 1):]  # keep the distinguishing tail
        labels.append(label)
    return labels


def _coverage_embeddings(
    paths: list[Path],
    model_id: str,
    cancel_check: CancelCheck | None = None,
) -> "np.ndarray":
    """Image embeddings for the coverage plot using the selected model family.

    Dispatches to CLIP (open_clip), DINOv2, or Qwen via the shared embedding
    package. Each loader flattens to a 1D row so the stacked array is 2D (N, D)
    for PCA/UMAP regardless of the model's native feature shape.
    """
    from ...embedding.loaders import embed_images

    emb = embed_images(model_id, paths, cancel_check=cancel_check)
    check_cancel(cancel_check)
    return emb


def _embedding_meta(model_id: str) -> dict:
    from ...embedding import catalog

    spec = catalog.get(model_id)
    return {
        "embedding": spec.family if spec else "custom",
        "embedding_model": model_id,
    }


def _save_umap(embeddings, paths: list[Path], out_path: Path, model_id: str = "") -> dict:
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
    for i, label in enumerate(_point_labels(paths)):
        ax.annotate(label, (coords[i, 0], coords[i, 1]), fontsize=6, alpha=0.6)
    ax.set_title("Dataset Coverage — UMAP")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    rpt.ok(f"Coverage UMAP saved → {out_path}")
    return {
        "method": "umap",
        **_embedding_meta(model_id),
        "preprocess": "pca",
        "pca_components": int(pca_components),
    }


def _save_pca(embeddings, paths: list[Path], out_path: Path, model_id: str = "") -> dict:
    import matplotlib.pyplot as plt
    from sklearn.decomposition import PCA

    coords = PCA(n_components=2).fit_transform(embeddings)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(coords[:, 0], coords[:, 1], alpha=0.8, s=60)
    for i, label in enumerate(_point_labels(paths)):
        ax.annotate(label, (coords[i, 0], coords[i, 1]), fontsize=6, alpha=0.6)
    ax.set_title("Dataset Coverage — PCA")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    rpt.ok(f"Coverage PCA saved → {out_path}")
    return {
        "method": "pca",
        **_embedding_meta(model_id),
        "pca_components": 2,
    }
