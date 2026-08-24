"""QualityGateStep on an empty input folder still has to leave a report."""
import json

from prepare_lora_kit.pipeline.configs import QualityGateConfig
from prepare_lora_kit.steps.context import StepRunContext
from prepare_lora_kit.steps.quality_gate import run


def test_empty_input_writes_an_empty_report(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    report_path = tmp_path / "reports" / "QualityGateStep_report.json"

    report = run(
        input_dir,
        QualityGateConfig(),
        context=StepRunContext(
            output_dir=tmp_path / "output",
            report_path=report_path,
        ),
    )

    # The report is a per-image map, so "no images scored" is an empty one —
    # written rather than skipped, so the reports folder matches the run-state.
    assert report == {}
    assert json.loads(report_path.read_text(encoding="utf-8")) == {}
