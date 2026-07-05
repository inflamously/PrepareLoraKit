"""Deterministic mock CLIP embeddings for --mock CurateStep coverage plots."""
from __future__ import annotations
from pathlib import Path


def _mock_embeddings(paths: list[Path]) -> "np.ndarray":
    import numpy as np

    centers = np.asarray([
        [0.0, 0.0, 0.0, 1.0, 0.20, 0.10, 0.0, 1.0],
        [1.2, 0.2, 0.9, 0.1, 0.65, 0.25, 0.3, 1.0],
        [0.2, 1.1, 0.1, 0.8, 0.35, 0.80, 0.6, 1.0],
    ], dtype=np.float32)
    rows = []
    for index, path in enumerate(paths):
        name_value = (sum(path.name.encode("utf-8")) % 97) / 97.0
        if path.name.startswith(("mock_pca_", "mock_umap_")):
            cluster = index % len(centers)
            jitter = ((index // len(centers)) % 5 - 2) * 0.012
            row = centers[cluster].copy()
            row += np.asarray([
                jitter,
                -jitter,
                jitter * 0.5,
                -jitter * 0.5,
                name_value * 0.01,
                jitter * 0.25,
                -jitter * 0.25,
                0.0,
            ], dtype=np.float32)
        else:
            t = index / max(1, len(paths) - 1)
            row = np.asarray([
                2.0 + t,
                -0.8 + t * 0.4,
                np.sin(t * np.pi * 2.0),
                np.cos(t * np.pi * 2.0),
                name_value,
                (index % 5) / 5.0,
                (index % 7) / 7.0,
                1.0,
            ], dtype=np.float32)
        rows.append(row)
    return np.asarray(rows, dtype=np.float32)
