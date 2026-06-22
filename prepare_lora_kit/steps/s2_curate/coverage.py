"""CLIP coverage visualisation for Step 2 curation."""
from __future__ import annotations
from pathlib import Path

from ...utils import report as rpt


def _clip_embeddings(paths: list[Path]) -> "np.ndarray":
    import torch
    import numpy as np
    from PIL import Image
    from .clip_model import load_clip

    model, processor = load_clip()

    embeddings = []
    for p in paths:
        image = Image.open(p).convert("RGB")
        inputs = processor(images=image, return_tensors="pt")
        with torch.no_grad():
            feat = model.get_image_features(**inputs)
        # Flatten to 1D so the stacked array is 2D (N, D) for PCA/UMAP,
        # regardless of whether the model returns pooled (D,) or spatial (C,H,W) features.
        embeddings.append(feat[0].cpu().numpy().reshape(-1))
    return np.stack(embeddings)


def _save_umap(embeddings, paths: list[Path], out_path: Path) -> dict:
    import matplotlib.pyplot as plt
    from sklearn.decomposition import PCA
    from umap import UMAP

    pca_components = min(50, embeddings.shape[0] - 1, embeddings.shape[1])
    reduced = PCA(n_components=pca_components).fit_transform(embeddings)
    reducer = UMAP(n_components=2, random_state=42)
    coords = reducer.fit_transform(reduced)

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.scatter(coords[:, 0], coords[:, 1], alpha=0.7, s=60)
    dense_clusters = _highlight_dense_clusters(ax, coords)
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
        "dense_clusters": dense_clusters,
    }


def _save_pca(embeddings, paths: list[Path], out_path: Path) -> dict:
    import matplotlib.pyplot as plt
    from sklearn.decomposition import PCA

    coords = PCA(n_components=2).fit_transform(embeddings)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(coords[:, 0], coords[:, 1], alpha=0.8, s=60)
    dense_clusters = _highlight_dense_clusters(ax, coords)
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
        "dense_clusters": dense_clusters,
    }


def _highlight_dense_clusters(ax, coords) -> list[dict]:
    import numpy as np
    from matplotlib.patches import Ellipse

    coords = np.asarray(coords, dtype=float)
    if coords.ndim != 2 or coords.shape[0] < 3 or coords.shape[1] < 2:
        return []

    xy = coords[:, :2]
    mins = xy.min(axis=0)
    spans = xy.max(axis=0) - mins
    spans = np.where(spans == 0, 1.0, spans)
    norm = (xy - mins) / spans

    distances = np.linalg.norm(norm[:, None, :] - norm[None, :, :], axis=2)
    np.fill_diagonal(distances, np.inf)
    nearest_count = min(3, len(xy) - 1)
    nearest = np.sort(distances, axis=1)[:, nearest_count - 1]
    finite_nearest = nearest[np.isfinite(nearest)]
    if len(finite_nearest) == 0:
        return []

    eps = float(np.clip(np.percentile(finite_nearest, 35) * 1.8, 0.045, 0.18))
    min_points = max(3, min(6, len(xy) // 8))
    labels = _dense_cluster_labels(distances, eps=eps, min_points=min_points)

    clusters = []
    for label in sorted(set(labels)):
        if label < 0:
            continue
        members = np.flatnonzero(labels == label)
        if len(members) < min_points:
            continue

        points = xy[members]
        center = points.mean(axis=0)
        width = max(float(points[:, 0].max() - points[:, 0].min()), spans[0] * 0.035)
        height = max(float(points[:, 1].max() - points[:, 1].min()), spans[1] * 0.035)
        ellipse = Ellipse(
            center,
            width * 1.45,
            height * 1.45,
            fill=False,
            edgecolor="#d62728",
            linestyle="--",
            linewidth=1.2,
            alpha=0.35,
            zorder=1,
        )
        ax.add_patch(ellipse)
        clusters.append({
            "points": int(len(members)),
            "center": [float(center[0]), float(center[1])],
        })

    return clusters


def _dense_cluster_labels(distances, *, eps: float, min_points: int) -> "np.ndarray":
    import numpy as np

    labels = np.full(distances.shape[0], -1, dtype=int)
    visited = np.zeros(distances.shape[0], dtype=bool)
    cluster_id = 0

    for index in range(distances.shape[0]):
        if visited[index]:
            continue
        visited[index] = True
        neighbors = set(np.flatnonzero(distances[index] <= eps).tolist())
        neighbors.add(index)
        if len(neighbors) < min_points:
            continue

        labels[index] = cluster_id
        seeds = set(neighbors)
        while seeds:
            current = seeds.pop()
            if not visited[current]:
                visited[current] = True
                current_neighbors = set(
                    np.flatnonzero(distances[current] <= eps).tolist()
                )
                current_neighbors.add(current)
                if len(current_neighbors) >= min_points:
                    seeds.update(current_neighbors)
            if labels[current] < 0:
                labels[current] = cluster_id
        cluster_id += 1

    return labels
