"""UI bridge against the folder-shaped project library.

Isolation comes from the suite-wide autouse ``isolated_projects`` fixture; these
tests take it as an argument only when they need the path.
"""
import os
from pathlib import Path

import yaml

from prepare_lora_kit.project import project_registry, store
from prepare_lora_kit_ui.bridge import UiBridge
from prepare_lora_kit_ui.runner import PipelineJob


def _write_project(name: str, **index_fields) -> Path:
    """Create a minimal project folder: an index with no step files.

    A listed step with no ``<step>.yaml`` runs on built-in defaults, so an index
    alone is a valid project — which keeps these bridge tests focused.
    """
    directory = store.project_dir_for_name(name)
    directory.mkdir(parents=True, exist_ok=True)
    data = {"name": name, **index_fields, "pipeline": [{"step": "import", "enabled": True}]}
    (directory / "index.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    return directory


def test_bridge_folder_first_creates_missing_project(isolated_projects, tmp_path):
    input_dir = tmp_path / "new-dataset"
    input_dir.mkdir()

    result = UiBridge().load_or_create_project_for_input(str(input_dir))
    index = yaml.safe_load(
        (isolated_projects / "new_dataset" / "index.yaml").read_text()
    )

    assert result["project_name"] == "new-dataset"
    assert result["input_dir"] == str(input_dir.resolve())
    assert result["project"]["input_dir"] == str(input_dir.resolve())
    assert Path(result["output_dir"]).parts[-2:] == ("outputs", "new-dataset")
    assert index["input_dir"] == str(input_dir.resolve())
    # A created project is a full folder, not just an index.
    assert (isolated_projects / "new_dataset" / "caption_bbox.yaml").exists()


def test_bridge_folder_first_updates_existing_project_without_losing_pipeline(
    isolated_projects, tmp_path
):
    input_dir = tmp_path / "existing"
    input_dir.mkdir()
    project_registry.create_project("existing")
    directory = isolated_projects / "existing"
    quality_gate = directory / "quality_gate.yaml"
    quality_gate.write_text(quality_gate.read_text() + "auto_only: true\n")
    before = quality_gate.read_bytes()

    result = UiBridge().load_or_create_project_for_input(str(input_dir))

    assert result["project_name"] == "existing"
    assert result["project"]["input_dir"] == str(input_dir.resolve())
    assert [step["type"] for step in result["project"]["steps"]][:3] == [
        "ImportStep",
        "QualityGateStep",
        "CurateStep",
    ]
    # Opening a folder rewrites index.yaml only; tuned step settings are untouched.
    assert quality_gate.read_bytes() == before


def test_bridge_load_project_returns_saved_input_dir_and_default_output(tmp_path):
    input_dir = tmp_path / "saved-dataset"
    input_dir.mkdir()
    _write_project("saved", input_dir=str(input_dir))

    result = UiBridge().load_project("saved")

    assert result["input_dir"] == str(input_dir)
    assert result["project"]["input_dir"] == str(input_dir)
    assert Path(result["output_dir"]).parts[-2:] == ("outputs", "saved-dataset")


def test_bridge_load_project_reports_missing_output_folder(tmp_path):
    input_dir = tmp_path / "saved-dataset"
    input_dir.mkdir()
    _write_project(
        "saved",
        input_dir=str(input_dir),
        output_dir=str(tmp_path / "outputs" / "saved-dataset"),
    )

    assert UiBridge().load_project("saved")["output_exists"] is False


def test_bridge_load_project_reports_existing_output_folder(tmp_path):
    input_dir = tmp_path / "saved-dataset"
    input_dir.mkdir()
    output_dir = tmp_path / "outputs" / "saved-dataset"
    output_dir.mkdir(parents=True)
    _write_project("saved", input_dir=str(input_dir), output_dir=str(output_dir))

    assert UiBridge().load_project("saved")["output_exists"] is True


def test_bridge_folder_first_reports_output_folder_existence(tmp_path):
    input_dir = tmp_path / "new-dataset"
    input_dir.mkdir()
    output_dir = tmp_path / "outputs" / "new-dataset"

    missing = UiBridge().load_or_create_project_for_input(
        str(input_dir), str(output_dir)
    )
    output_dir.mkdir(parents=True)
    present = UiBridge().load_or_create_project_for_input(
        str(input_dir), str(output_dir)
    )

    assert missing["output_exists"] is False
    assert present["output_exists"] is True


# ── library cards ─────────────────────────────────────────────────────────────

def test_project_card_mtime_comes_from_index_yaml(isolated_projects, tmp_path):
    """The library sorts by mtime; index.yaml is what every metadata write touches."""
    _write_project("older", input_dir=str(tmp_path / "a"))
    _write_project("newer", input_dir=str(tmp_path / "b"))
    os.utime(isolated_projects / "older" / "index.yaml", (1_000_000, 1_000_000))
    os.utime(isolated_projects / "newer" / "index.yaml", (2_000_000, 2_000_000))

    cards = {card["name"]: card for card in UiBridge().list_projects()["projects"]}

    assert cards["older"]["mtime"] == 1_000_000
    assert cards["newer"]["mtime"] == 2_000_000


def test_a_folder_without_an_index_is_not_listed(isolated_projects, tmp_path):
    _write_project("real", input_dir=str(tmp_path / "a"))
    (isolated_projects / "__pycache__").mkdir()

    names = [card["name"] for card in UiBridge().list_projects()["projects"]]

    assert names == ["real"]


def test_project_card_survives_an_unreadable_step_file(isolated_projects, tmp_path):
    """One broken step file must not cost the card its identity.

    Name and paths come from index.yaml, which is read without opening any step
    file, so the card stays recognisable and clickable. The failure is still
    surfaced — hiding it would be worse — but it no longer erases everything else.
    """
    project_registry.create_project("demo", input_dir=str(tmp_path / "images"))
    (isolated_projects / "demo" / "caption_bbox.yaml").write_text("{[not: valid\n")

    card = UiBridge().list_projects()["projects"][0]

    assert card["name"] == "demo"
    assert card["input_dir"] == str(tmp_path / "images")
    assert card["initials"] == "DE"
    assert card["mtime"] > 0
    assert "caption_bbox.yaml" in card["error"]
