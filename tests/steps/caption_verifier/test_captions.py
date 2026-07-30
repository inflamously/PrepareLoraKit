"""Tests for Caption Verifier caption discovery and write-back.

This is the only step in the pipeline that lets a human free-type directly into
training data, so the write path gets the most scrutiny: atomicity, path
containment, and never touching generated bbox region sidecars.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from prepare_lora_kit.steps.caption_verifier import captions


def _image(path: Path, caption: str | None = "a caption") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), "red").save(path)
    if caption is not None:
        path.with_suffix(".txt").write_text(caption, encoding="utf-8")
    return path


# --- discovery -------------------------------------------------------------

def test_collect_skips_images_without_a_caption_sidecar(tmp_path):
    _image(tmp_path / "with.png", "hello")
    _image(tmp_path / "without.png", None)

    found = captions.collect_verifiable_images(tmp_path)

    assert [item["name"] for item in found] == ["with.png"]
    assert found[0]["caption"] == "hello"


def test_collect_excludes_generated_bbox_region_artifacts(tmp_path):
    """plk_bbox__* crops are real images with real .txt sidecars in dataset/.

    A naive iter_images sweep would offer region crops as if they were source
    images, and editing their captions would desync them from boxes.json.
    """
    _image(tmp_path / "photo.png", "source caption")
    _image(tmp_path / "plk_bbox__photo__01.png", "region caption")

    found = captions.collect_verifiable_images(tmp_path)

    assert [item["name"] for item in found] == ["photo.png"]


def test_collect_recurses_into_subdirectories(tmp_path):
    _image(tmp_path / "nested" / "deep.png", "nested caption")

    found = captions.collect_verifiable_images(tmp_path)

    assert [item["name"] for item in found] == ["deep.png"]


def test_collect_respects_max_images(tmp_path):
    for index in range(5):
        _image(tmp_path / f"img_{index}.png", f"caption {index}")

    found = captions.collect_verifiable_images(tmp_path, max_images=2)

    assert len(found) == 2


def test_collect_reports_blank_captions_without_dropping_them(tmp_path):
    _image(tmp_path / "blank.png", "   ")

    found = captions.collect_verifiable_images(tmp_path)

    assert len(found) == 1
    assert found[0]["caption"] == ""


# --- atomic write ----------------------------------------------------------

def test_write_caption_atomic_leaves_no_temp_files(tmp_path):
    target = tmp_path / "img.txt"
    target.write_text("before", encoding="utf-8")

    captions.write_caption_atomic(target, "after")

    assert target.read_text(encoding="utf-8") == "after"
    assert list(tmp_path.glob("*.plk_tmp")) == []
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".")] == []


def test_write_caption_atomic_creates_a_missing_sidecar(tmp_path):
    target = tmp_path / "new.txt"

    captions.write_caption_atomic(target, "fresh")

    assert target.read_text(encoding="utf-8") == "fresh"


# --- apply edits -----------------------------------------------------------

def test_apply_edits_writes_changed_captions_and_skips_unchanged(tmp_path):
    changed = _image(tmp_path / "changed.png", "old text")
    same = _image(tmp_path / "same.png", "identical")

    applied, rejected = captions.apply_caption_edits(
        tmp_path,
        {
            str(changed): "new text",
            str(same): "identical",
        },
    )

    assert changed.with_suffix(".txt").read_text(encoding="utf-8") == "new text"
    assert same.with_suffix(".txt").read_text(encoding="utf-8") == "identical"
    assert [entry["path"] for entry in applied] == [str(changed)]
    assert rejected == []


def test_apply_edits_rejects_empty_captions_and_preserves_the_original(tmp_path):
    """An empty .txt would make AuditStep flag the image and ExportStep still ship it."""
    image = _image(tmp_path / "img.png", "keep me")

    applied, rejected = captions.apply_caption_edits(tmp_path, {str(image): "   "})

    assert image.with_suffix(".txt").read_text(encoding="utf-8") == "keep me"
    assert applied == []
    assert rejected
    assert rejected[0]["reason"] == "empty caption"


def test_apply_edits_rejects_paths_outside_the_dataset_dir(tmp_path):
    """Keys arrive over the pywebview bridge from JS and are untrusted."""
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    _image(dataset / "inside.png", "inside")
    outside = _image(tmp_path / "outside.png", "outside")

    applied, rejected = captions.apply_caption_edits(dataset, {str(outside): "hacked"})

    assert outside.with_suffix(".txt").read_text(encoding="utf-8") == "outside"
    assert applied == []
    assert rejected
    assert rejected[0]["reason"] == "outside dataset"


def test_apply_edits_never_touches_bbox_region_sidecars(tmp_path):
    region = _image(tmp_path / "plk_bbox__photo__01.png", "region caption")

    applied, rejected = captions.apply_caption_edits(tmp_path, {str(region): "rewritten"})

    assert region.with_suffix(".txt").read_text(encoding="utf-8") == "region caption"
    assert applied == []
    assert rejected
    assert rejected[0]["reason"] == "bbox region artifact"


def test_apply_edits_only_strips_and_never_renormalizes(tmp_path):
    """A 'wrong' verdict means the user deliberately removed a term.

    Re-injecting the concept token or re-running caption cleanup would defeat
    the entire feature, so the text is stored as typed apart from stripping.
    """
    image = _image(tmp_path / "img.png", "tok, a wrinkled face")

    captions.apply_caption_edits(tmp_path, {str(image): "  a smooth grey cylinder \n"})

    assert image.with_suffix(".txt").read_text(encoding="utf-8") == (
        "a smooth grey cylinder"
    )


def test_apply_edits_writes_a_backup_before_the_first_write(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    image = _image(dataset / "nested" / "img.png", "original")
    backup_dir = tmp_path / "captions_before"

    captions.apply_caption_edits(
        dataset, {str(image): "edited"}, backup_dir=backup_dir,
    )

    assert (backup_dir / "nested" / "img.txt").read_text(encoding="utf-8") == "original"
    assert image.with_suffix(".txt").read_text(encoding="utf-8") == "edited"


def test_apply_edits_ignores_unknown_paths(tmp_path):
    applied, rejected = captions.apply_caption_edits(
        tmp_path, {str(tmp_path / "ghost.png"): "text"},
    )

    assert applied == []
    assert rejected
    assert rejected[0]["reason"] == "missing image"
