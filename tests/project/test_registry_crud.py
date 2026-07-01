import pytest

from prepare_lora_kit.project import registry as project_registry


@pytest.fixture()
def isolated_configs(tmp_path, monkeypatch):
    """Point the project registry at an empty temp configs/projects dir."""
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    monkeypatch.setattr(project_registry._registry, "configs_dir", projects_dir)
    return projects_dir


def test_create_project_writes_defaulted_pipeline(isolated_configs):
    path = project_registry.create_project(
        "demo", network="flux-klein-9b", input_dir="/data/in", output_dir="/data/out"
    )
    assert path.exists()

    cfg = project_registry.load("demo")
    assert cfg.name == "demo"
    assert cfg.network == "flux-klein-9b"
    assert cfg.input_dir == "/data/in"
    assert cfg.output_dir == "/data/out"
    assert len(cfg.pipeline) == 10


def test_create_project_rejects_duplicate(isolated_configs):
    project_registry.create_project("demo")
    with pytest.raises(ValueError, match="already exists"):
        project_registry.create_project("demo")


def test_update_project_meta_rename_preserves_pipeline(isolated_configs):
    project_registry.create_project("demo", input_dir="/data/in")
    before = project_registry.load("demo")

    project_registry.update_project_meta(
        "demo", "renamed", network="flux-klein-9b", input_dir="/data/in2", output_dir=None
    )

    assert not project_registry.config_path_for_name("demo").exists()
    after = project_registry.load("renamed")
    assert after.name == "renamed"
    assert after.input_dir == "/data/in2"
    assert after.output_dir is None
    assert [s.type for s in after.pipeline] == [s.type for s in before.pipeline]


def test_duplicate_project_auto_names(isolated_configs):
    project_registry.create_project("demo")
    first = project_registry.duplicate_project("demo")
    second = project_registry.duplicate_project("demo")
    assert first == "demo_copy"
    assert second == "demo_copy2"
    assert project_registry.load("demo_copy").name == "demo_copy"


def test_delete_project_is_idempotent(isolated_configs):
    project_registry.create_project("demo")
    project_registry.delete_project("demo")
    assert not project_registry.config_path_for_name("demo").exists()
    # Second delete must not raise.
    project_registry.delete_project("demo")
