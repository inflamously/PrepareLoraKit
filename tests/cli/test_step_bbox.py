"""Tests for the CLI bbox region-annotation path of the `step` command."""
from pathlib import Path

from PIL import Image
import click
import pytest

from prepare_lora_kit.cli.step import _parse_bbox, _resolve_bbox_target
from prepare_lora_kit.interaction import CliBboxRegionProvider
from prepare_lora_kit.steps.s5_caption import step as caption_step


# ── _parse_bbox ────────────────────────────────────────────────────────────────

def test_parse_bbox_pixels_normalized_against_image_size():
    box = _parse_bbox("0,0,50,25", 100, 50)
    assert box == {"x1": 0.0, "y1": 0.0, "x2": 0.5, "y2": 0.5, "label": ""}


def test_parse_bbox_with_label():
    box = _parse_bbox("10,10,90,90:a red car", 100, 100)
    assert box["label"] == "a red car"
    assert (box["x1"], box["y1"], box["x2"], box["y2"]) == (0.1, 0.1, 0.9, 0.9)


def test_parse_bbox_already_normalized_passthrough():
    # All four values <= 1.0 → treated as normalized, not divided by (1000, 800).
    box = _parse_bbox("0,0,0.5,0.5", 1000, 800)
    assert (box["x1"], box["y1"], box["x2"], box["y2"]) == (0.0, 0.0, 0.5, 0.5)


def test_parse_bbox_out_of_order_sorted():
    box = _parse_bbox("80,60,20,10", 100, 100)
    assert box["x1"] < box["x2"] and box["y1"] < box["y2"]
    assert (box["x1"], box["x2"]) == (0.2, 0.8)


def test_parse_bbox_clamps_out_of_bounds():
    box = _parse_bbox("-10,-10,200,200", 100, 100)
    assert (box["x1"], box["y1"], box["x2"], box["y2"]) == (0.0, 0.0, 1.0, 1.0)


def test_parse_bbox_rejects_wrong_arity():
    with pytest.raises(click.BadParameter):
        _parse_bbox("1,2,3", 100, 100)


def test_parse_bbox_rejects_non_numeric():
    with pytest.raises(click.BadParameter):
        _parse_bbox("1,2,three,4", 100, 100)


# ── _resolve_bbox_target ───────────────────────────────────────────────────────

def test_resolve_bbox_target_single_image_default(tmp_path):
    img = tmp_path / "only.png"
    Image.new("RGB", (8, 8), "blue").save(img)
    assert _resolve_bbox_target(tmp_path, None) == img


def test_resolve_bbox_target_requires_selection_when_ambiguous(tmp_path):
    Image.new("RGB", (8, 8), "blue").save(tmp_path / "a.png")
    Image.new("RGB", (8, 8), "blue").save(tmp_path / "b.png")
    with pytest.raises(click.BadParameter):
        _resolve_bbox_target(tmp_path, None)


def test_resolve_bbox_target_named_missing(tmp_path):
    Image.new("RGB", (8, 8), "blue").save(tmp_path / "a.png")
    with pytest.raises(click.BadParameter):
        _resolve_bbox_target(tmp_path, "nope.png")


# ── CliBboxRegionProvider ──────────────────────────────────────────────────────

def test_provider_returns_boxes_for_target_without_cropping(tmp_path):
    img = tmp_path / "image.png"
    Image.new("RGB", (8, 8), "blue").save(img)
    boxes = [{"x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5, "label": "face"}]
    provider = CliBboxRegionProvider(img, boxes)

    captioner_calls = []
    annotations, skipped, skip_all = provider.annotate_image(
        img, captioner=lambda *a, **k: captioner_calls.append(a) or {})

    assert (skipped, skip_all) == (False, False)
    assert annotations == boxes
    assert captioner_calls == []  # region-context-only: never crops/captions


def test_provider_skips_non_target_image(tmp_path):
    img = tmp_path / "image.png"
    other = tmp_path / "other.png"
    Image.new("RGB", (8, 8), "blue").save(img)
    provider = CliBboxRegionProvider(img, [{"x1": 0, "y1": 0, "x2": 1, "y2": 1, "label": ""}])

    assert provider.annotate_image(other) == ([], True, False)


# ── Integration: annotations reach caption_image, no plk_bbox__ artifacts ───────

def _fake_runtime_class(captured):
    class FakeRuntime:
        def __init__(self, model_id, *, task, quantization, dtype, max_pixels,
                     status_callback=None, caption_prompt=None, region_prompt=None):
            self.metadata = {"model_id": model_id, "adapter": "fake", "device": "cpu"}
            self.status = {"phase": "ready", "message": "ok"}

        def load(self):
            pass

        def caption_region(self, crop):  # pragma: no cover - must not be called
            raise AssertionError("region captioning must not run in region-context-only mode")

        def caption_image(self, path, annotations, concept_token, *, max_new_tokens):
            captured.append((Path(path).name, [dict(a) for a in annotations]))
            return "whole caption"

        def unload(self):
            pass

    return FakeRuntime


def test_bbox_annotations_reach_caption_image(tmp_path, monkeypatch):
    img = tmp_path / "image.png"
    Image.new("RGB", (16, 12), "blue").save(img)
    captured = []
    monkeypatch.setattr(caption_step.vlm, "CaptionRuntime", _fake_runtime_class(captured))

    boxes = [{"x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.6, "label": "face"}]
    caption_step.run(
        tmp_path,
        concept_token="tok",
        output_dir=tmp_path,
        caption_model_id="fake/model",
        interaction=CliBboxRegionProvider(img, boxes),
        enabled_substeps=["s5_1_annotate", "s5_2_caption"],
        spot_check_pct=0,
    )

    assert len(captured) == 1
    name, annotations = captured[0]
    assert name == "image.png"
    assert annotations == boxes
    assert (tmp_path / "image.txt").exists()
    # Region-context-only: no per-region crop/training-pair artifacts are produced.
    # (A plk_bbox__*__boxes.json reload sidecar may exist — that is metadata, not a crop.)
    assert not list(tmp_path.glob("plk_bbox__*.png"))
    assert not list(tmp_path.glob("plk_bbox__*__[0-9][0-9].txt"))
