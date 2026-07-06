"""Tests for per-image bbox-coordinate sidecars (reload support, Step 5)."""
from PIL import Image

from prepare_lora_kit.steps.caption_bbox.artifacts import (
    _boxes_sidecar_path,
    _is_bbox_artifact,
    load_boxes_sidecar,
    save_boxes_sidecar,
)


def _source(tmp_path):
    src = tmp_path / "image.png"
    Image.new("RGB", (16, 12), "blue").save(src)
    return src


def test_boxes_sidecar_path_uses_bbox_prefix(tmp_path):
    src = _source(tmp_path)
    sidecar = _boxes_sidecar_path(src)
    assert sidecar == tmp_path / "plk_bbox__image__boxes.json"
    # Prefixed so --force cleanup removes it and it is excluded from caption sources.
    assert _is_bbox_artifact(sidecar)


def test_save_and_load_roundtrip_keeps_coords_and_labels(tmp_path):
    src = _source(tmp_path)
    annotations = [
        {"x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.6, "label": "a red car",
         "crop_name": "plk_bbox__image__01.png", "crop_path": "/ignored", "extra": "drop"},
        {"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0, "label": "background"},
    ]
    save_boxes_sidecar(src, annotations)

    loaded = load_boxes_sidecar(src)
    assert len(loaded) == 2
    first = loaded[0]
    assert (first["x1"], first["y1"], first["x2"], first["y2"]) == (0.1, 0.2, 0.5, 0.6)
    assert first["label"] == "a red car"
    assert first["crop_name"] == "plk_bbox__image__01.png"
    # Only the known fields are persisted.
    assert "extra" not in first
    assert loaded[1]["label"] == "background"
    assert "crop_name" not in loaded[1]


def test_load_resolves_crop_paths_when_files_exist(tmp_path):
    src = _source(tmp_path)
    crop = tmp_path / "plk_bbox__image__01.png"
    Image.new("RGB", (4, 4), "green").save(crop)
    (tmp_path / "plk_bbox__image__01.txt").write_text("tok, a red car", encoding="utf-8")

    save_boxes_sidecar(src, [
        {"x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5, "label": "a red car",
         "crop_name": "plk_bbox__image__01.png"},
    ])
    loaded = load_boxes_sidecar(src)

    assert loaded[0]["crop_path"] == str(crop)
    assert loaded[0]["sidecar_path"] == str(tmp_path / "plk_bbox__image__01.txt")


def test_load_omits_crop_paths_when_crop_missing(tmp_path):
    src = _source(tmp_path)
    save_boxes_sidecar(src, [
        {"x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5, "label": "x",
         "crop_name": "plk_bbox__image__99.png"},
    ])
    loaded = load_boxes_sidecar(src)
    assert "crop_path" not in loaded[0]
    assert "sidecar_path" not in loaded[0]


def test_save_empty_annotations_removes_existing_sidecar(tmp_path):
    src = _source(tmp_path)
    save_boxes_sidecar(src, [{"x1": 0, "y1": 0, "x2": 1, "y2": 1, "label": "x"}])
    assert _boxes_sidecar_path(src).exists()

    save_boxes_sidecar(src, [])
    assert not _boxes_sidecar_path(src).exists()
    assert load_boxes_sidecar(src) == []


def test_load_missing_or_corrupt_sidecar_returns_empty(tmp_path):
    src = _source(tmp_path)
    assert load_boxes_sidecar(src) == []

    _boxes_sidecar_path(src).write_text("{not json", encoding="utf-8")
    assert load_boxes_sidecar(src) == []
