import json

import pytest
from PIL import Image

from prepare_lora_kit.cancellation import CancelledRun
from prepare_lora_kit.steps.s0_import import run


def test_import_step_copies_images_and_writes_report(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    report_path = tmp_path / "reports" / "ImportStep_report.json"
    input_dir.mkdir()
    Image.new("RGB", (16, 16), "red").save(input_dir / "first.png")
    Image.new("RGB", (16, 16), "blue").save(input_dir / "second.jpg")
    (input_dir / "notes.txt").write_text("not an image", encoding="utf-8")

    report = run(input_dir, output_dir, report_path=report_path)

    assert sorted(path.name for path in output_dir.iterdir()) == ["first.png", "second.jpg"]
    assert report["count"] == 2
    assert report_path.exists()
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["count"] == 2
    assert len(saved["imported"]) == 2


def test_import_step_removes_partial_output_when_cancelled(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    Image.new("RGB", (16, 16), "red").save(input_dir / "first.png")
    Image.new("RGB", (16, 16), "blue").save(input_dir / "second.jpg")
    checks = 0

    def cancel_after_first_copy():
        nonlocal checks
        checks += 1
        if checks >= 3:
            raise CancelledRun("Run cancelled")

    with pytest.raises(CancelledRun):
        run(input_dir, output_dir, cancel_check=cancel_after_first_copy)

    assert not output_dir.exists()
