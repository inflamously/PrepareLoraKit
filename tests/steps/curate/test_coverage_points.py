"""Unit tests for coverage-plot per-point hover coordinates."""
import numpy as np

from prepare_lora_kit.steps.curate.coverage import _save_pca, _save_umap


def _fake_paths(tmp_path, count):
    paths = []
    for i in range(count):
        path = tmp_path / f"img_{i}.png"
        path.write_bytes(b"")
        paths.append(path)
    return paths


def _assert_valid_points(points, paths):
    assert len(points) == len(paths)
    for point, path in zip(points, paths):
        assert point["path"] == str(path)
        assert 0 <= point["x_pct"] <= 100
        assert 0 <= point["y_pct"] <= 100


def test_save_pca_returns_per_point_percentages(tmp_path):
    paths = _fake_paths(tmp_path, 4)
    embeddings = np.random.default_rng(0).normal(size=(4, 6))
    out_path = tmp_path / "coverage_pca.png"

    result = _save_pca(embeddings, paths, out_path)

    assert out_path.is_file()
    _assert_valid_points(result["points"], paths)


def test_save_umap_returns_per_point_percentages(tmp_path):
    paths = _fake_paths(tmp_path, 10)
    embeddings = np.random.default_rng(0).normal(size=(10, 6))
    out_path = tmp_path / "coverage_umap.png"

    result = _save_umap(embeddings, paths, out_path)

    assert out_path.is_file()
    _assert_valid_points(result["points"], paths)
