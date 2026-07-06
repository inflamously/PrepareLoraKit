"""Tests for the ExportStep diff computation."""
from __future__ import annotations

from pathlib import Path

from prepare_lora_kit.steps.export_step.diff import compute_diff


def _write(path: Path, content: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)


def _dataset(root: Path) -> Path:
    """A finalized dataset: two captioned images (one nested) + one uncaptioned."""
    ds = root / "dataset"
    _write(ds / "subject" / "image_01.png", b"IMG-1")
    _write(ds / "subject" / "image_01.txt", "a caption")
    _write(ds / "image_02.png", b"IMG-2")
    _write(ds / "image_02.txt", "another caption")
    _write(ds / "no_caption.png", b"IMG-3")  # not finalized
    return ds


def test_all_added_when_target_missing(tmp_path):
    ds = _dataset(tmp_path)
    diff = compute_diff(ds, tmp_path / "export")

    rels = sorted(e.rel for e in diff.added)
    assert rels == ["image_02.png", "subject/image_01.png"]
    assert diff.counts() == {"added": 2, "modified": 0, "unchanged": 0, "orphaned": 0}
    # The uncaptioned image is never part of the export plan.
    all_rels = {e.rel for e in diff.changed} | {e.rel for e in diff.unchanged}
    assert "no_caption.png" not in all_rels


def test_unchanged_when_target_identical(tmp_path):
    ds = _dataset(tmp_path)
    target = tmp_path / "export"
    _write(target / "subject" / "image_01.png", b"IMG-1")
    _write(target / "subject" / "image_01.txt", "a caption")
    _write(target / "image_02.png", b"IMG-2")
    _write(target / "image_02.txt", "another caption")

    diff = compute_diff(ds, target)

    assert diff.counts() == {"added": 0, "modified": 0, "unchanged": 2, "orphaned": 0}


def test_modified_when_image_differs(tmp_path):
    ds = _dataset(tmp_path)
    target = tmp_path / "export"
    _write(target / "subject" / "image_01.png", b"OLD-DIFFERENT-BYTES")
    _write(target / "subject" / "image_01.txt", "a caption")
    _write(target / "image_02.png", b"IMG-2")
    _write(target / "image_02.txt", "another caption")

    diff = compute_diff(ds, target)

    modified = [e.rel for e in diff.modified]
    assert modified == ["subject/image_01.png"]
    assert diff.counts()["unchanged"] == 1


def test_modified_when_only_caption_differs(tmp_path):
    ds = _dataset(tmp_path)
    target = tmp_path / "export"
    _write(target / "subject" / "image_01.png", b"IMG-1")
    _write(target / "subject" / "image_01.txt", "stale caption")  # differs
    _write(target / "image_02.png", b"IMG-2")
    _write(target / "image_02.txt", "another caption")

    diff = compute_diff(ds, target)

    entry = next(e for e in diff.modified if e.rel == "subject/image_01.png")
    assert entry.image_status == "unchanged"
    assert entry.caption_status == "modified"


def test_orphaned_reported_not_removed(tmp_path):
    ds = _dataset(tmp_path)
    target = tmp_path / "export"
    _write(target / "old_reject.png", b"STALE")  # not in the final set

    diff = compute_diff(ds, target)

    assert diff.orphaned == ["old_reject.png"]
    assert diff.counts()["orphaned"] == 1
    # Diff computation must never touch the target.
    assert (target / "old_reject.png").exists()
