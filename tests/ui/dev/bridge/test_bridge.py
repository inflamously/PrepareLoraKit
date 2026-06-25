from prepare_lora_kit.ui.bridge import UiBridge
from prepare_lora_kit.ui.e2e import create_mock_ui_fixture


def test_bridge_exposes_in_memory_mock_project(tmp_path):
    fixture = create_mock_ui_fixture("CurateStep", root=tmp_path / "mock")
    bridge = UiBridge(
        projects={fixture.project.name: fixture.project},
        bootstrap=fixture.bootstrap_payload(),
    )

    names = [card["name"] for card in bridge.list_projects()["projects"]]
    assert fixture.project.name in names

    info = bridge.app_info()
    assert info["bootstrap"]["project"] == fixture.project.name

    result = bridge.load_project(fixture.project.name, str(fixture.output_dir))
    assert result["project_name"] == fixture.project.name
    assert result["input_dir"] == str(fixture.input_dir)
    assert result["output_dir"] == str(fixture.output_dir)
