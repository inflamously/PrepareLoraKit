import pytest

from prepare_lora_kit_ui.e2e import MOCK_PROJECT_NAME, create_mock_ui_fixture
from prepare_lora_kit.utils.state import RunState


def test_mock_fixture_generates_dataset_and_prerequisite_state(tmp_path):
    fixture = create_mock_ui_fixture("AuditStep", root=tmp_path / "mock")

    assert fixture.project.name == MOCK_PROJECT_NAME
    assert fixture.selected_steps == ["AuditStep"]
    assert len(list(fixture.input_dir.glob("*.png"))) == 5
    assert len(list((fixture.output_dir / "dataset").glob("*.png"))) == 4
    assert len(list((fixture.output_dir / "dataset").glob("*.txt"))) == 5
    assert (fixture.input_dir / "mock_bad_too_small.png").exists()
    assert not (fixture.output_dir / "dataset" / "mock_bad_too_small.png").exists()

    state = RunState(fixture.output_dir)
    assert state.is_done("ImportStep")
    assert state.is_done("QualityGateStep")
    assert state.is_done("VaeGateStep")
    assert state.is_done("CaptionStep")
    assert not state.is_done("AuditStep")


def test_mock_fixture_does_not_seed_captions_before_caption_step(tmp_path):
    fixture = create_mock_ui_fixture("CurateStep", root=tmp_path / "mock")

    assert len(list((fixture.output_dir / "dataset").glob("*.png"))) == 4
    assert not (fixture.output_dir / "dataset" / "mock_bad_too_small.png").exists()
    assert not list((fixture.output_dir / "dataset").glob("*.txt"))
    assert RunState(fixture.output_dir).is_done("ImportStep")
    assert RunState(fixture.output_dir).is_done("QualityGateStep")
    assert not RunState(fixture.output_dir).is_done("CurateStep")


def test_mock_import_fixture_starts_without_working_dataset(tmp_path):
    fixture = create_mock_ui_fixture("ImportStep", root=tmp_path / "mock")

    assert len(list(fixture.input_dir.glob("*.png"))) == 5
    assert not (fixture.output_dir / "dataset").exists()
    assert not RunState(fixture.output_dir).is_done("ImportStep")


def test_mock_quality_gate_fixture_includes_reviewable_good_and_bad_images(tmp_path):
    fixture = create_mock_ui_fixture("QualityGateStep", root=tmp_path / "mock")
    quality_config = next(
        step.config for step in fixture.project.pipeline if step.type == "QualityGateStep"
    )

    assert len(list(fixture.input_dir.glob("*.png"))) == 5
    assert len(list((fixture.output_dir / "dataset").glob("*.png"))) == 5
    assert quality_config.auto_only is False
    assert RunState(fixture.output_dir).is_done("ImportStep")
    assert [(s.name, s.op, s.threshold) for s in quality_config.scorers] == [
        ("min_side", "lt", 1024.0)
    ]


def test_mock_fixture_rejects_non_empty_unmarked_root(tmp_path):
    root = tmp_path / "not-dedicated"
    root.mkdir()
    (root / "input").mkdir()

    with pytest.raises(ValueError, match="Mock output root must be empty"):
        create_mock_ui_fixture("CurateStep", root=root)
