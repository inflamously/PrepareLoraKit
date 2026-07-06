"""End-to-end tests for ExportStep.run()."""
from __future__ import annotations

from pathlib import Path

from prepare_lora_kit.steps.export_step import run


def _write(path: Path, content: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)


def _dataset(root: Path) -> Path:
    ds = root / "out" / "dataset"
    _write(ds / "subject" / "image_01.png", b"IMG-1")
    _write(ds / "subject" / "image_01.txt", "caption one")
    _write(ds / "image_02.png", b"IMG-2")
    _write(ds / "image_02.txt", "caption two")
    _write(ds / "no_caption.png", b"IMG-3")  # not finalized — never exported
    return ds


class FakeProvider:
    """Records the review payload and returns a canned decision."""

    def __init__(self, confirmed=True, excluded=None):
        self.confirmed = confirmed
        self.excluded = list(excluded or [])
        self.payload = None

    def export_review(self, payload):
        self.payload = payload
        return {"confirmed": self.confirmed, "excluded": self.excluded}


def _dataset_snapshot(ds: Path) -> dict[str, bytes]:
    return {str(p.relative_to(ds)): p.read_bytes() for p in ds.rglob("*") if p.is_file()}


def test_export_copies_pairs_preserving_subfolders(tmp_path):
    ds = _dataset(tmp_path)
    target = tmp_path / "export"
    before = _dataset_snapshot(ds)
    provider = FakeProvider(confirmed=True)

    report = run(
        ds,
        original_dir=tmp_path / "input",
        target_dir=str(target),
        output_dir=tmp_path / "out",
        interaction=provider,
    )

    # Image + caption pairs copied, subject subfolder preserved.
    assert (target / "subject" / "image_01.png").read_bytes() == b"IMG-1"
    assert (target / "subject" / "image_01.txt").read_text() == "caption one"
    assert (target / "image_02.png").read_bytes() == b"IMG-2"
    assert (target / "image_02.txt").read_text() == "caption two"
    # Uncaptioned image is not exported.
    assert not (target / "no_caption.png").exists()
    # The working dataset is untouched.
    assert _dataset_snapshot(ds) == before
    assert report["exported"] is True
    assert report["counts"]["added"] == 2
    assert len(report["copied"]) == 2


def test_default_target_is_sibling_of_input(tmp_path):
    ds = _dataset(tmp_path)
    provider = FakeProvider(confirmed=True)

    report = run(
        ds,
        original_dir=tmp_path / "input",
        target_dir=None,
        output_dir=tmp_path / "out",
        interaction=provider,
    )

    expected = tmp_path / "input_export"
    assert report["target_dir"] == str(expected)
    assert (expected / "image_02.png").exists()


def test_cancel_writes_nothing(tmp_path):
    ds = _dataset(tmp_path)
    target = tmp_path / "export"
    provider = FakeProvider(confirmed=False)

    report = run(
        ds,
        original_dir=tmp_path / "input",
        target_dir=str(target),
        output_dir=tmp_path / "out",
        interaction=provider,
    )

    assert report["exported"] is False
    assert report["confirmed"] is False
    assert not target.exists()


def test_excluded_entries_are_skipped(tmp_path):
    ds = _dataset(tmp_path)
    target = tmp_path / "export"
    provider = FakeProvider(confirmed=True, excluded=["image_02.png"])

    run(
        ds,
        original_dir=tmp_path / "input",
        target_dir=str(target),
        output_dir=tmp_path / "out",
        interaction=provider,
    )

    assert (target / "subject" / "image_01.png").exists()
    assert not (target / "image_02.png").exists()
    assert not (target / "image_02.txt").exists()


def test_orphaned_left_in_place_and_reported(tmp_path):
    ds = _dataset(tmp_path)
    target = tmp_path / "export"
    _write(target / "old_reject.png", b"STALE")
    provider = FakeProvider(confirmed=True)

    report = run(
        ds,
        original_dir=tmp_path / "input",
        target_dir=str(target),
        output_dir=tmp_path / "out",
        interaction=provider,
    )

    assert (target / "old_reject.png").read_bytes() == b"STALE"
    assert report["orphaned"] == ["old_reject.png"]
    # The review payload the provider saw included the orphan.
    assert provider.payload["orphaned"] == ["old_reject.png"]


def test_report_written_to_reports_dir(tmp_path):
    ds = _dataset(tmp_path)
    provider = FakeProvider(confirmed=True)

    run(
        ds,
        original_dir=tmp_path / "input",
        target_dir=str(tmp_path / "export"),
        output_dir=tmp_path / "out",
        interaction=provider,
    )

    assert (tmp_path / "out" / "reports" / "ExportStep_report.json").is_file()


def test_diff_substep_disabled_exports_without_review(tmp_path):
    ds = _dataset(tmp_path)
    target = tmp_path / "export"

    # No interaction provider and preview_export_diff disabled: exports unconditionally.
    report = run(
        ds,
        original_dir=tmp_path / "input",
        target_dir=str(target),
        output_dir=tmp_path / "out",
        interaction=None,
        enabled_substeps=["copy_export"],
    )

    assert report["exported"] is True
    assert (target / "image_02.png").exists()
