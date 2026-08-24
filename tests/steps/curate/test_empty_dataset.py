"""CurateStep on a dataset with nothing in it still has to leave a report."""
import json

from prepare_lora_kit.pipeline.configs import CurateConfig
from prepare_lora_kit.steps.context import StepRunContext
from prepare_lora_kit.steps.curate import run


def test_empty_dataset_writes_a_skipped_report(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    report_path = tmp_path / "reports" / "CurateStep_report.json"

    report = run(
        dataset_dir,
        CurateConfig(),
        context=StepRunContext(
            output_dir=tmp_path / "output",
            report_path=report_path,
        ),
    )

    assert report["skipped"] is True
    assert report["reason"] == "no images"
    assert report["kept_images"] == []
    assert json.loads(report_path.read_text(encoding="utf-8")) == report


def test_skipped_report_keeps_the_key_set_of_a_successful_one(tmp_path):
    """The UI renders one report shape; a no-work run must not drop keys."""

    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()

    report = run(
        dataset_dir,
        CurateConfig(),
        context=StepRunContext(
            output_dir=tmp_path / "out",
            report_path=tmp_path / "reports" / "CurateStep_report.json",
        ),
    )

    assert set(report) >= {
        "duplicate_pairs",
        "dropped_duplicates",
        "duplicate_drop_candidates",
        "kept_images",
        "coverage_image",
        "coverage",
        "substeps",
    }
    assert set(report["substeps"]) == {"duplicate_check", "clip_scan", "drop_images"}
