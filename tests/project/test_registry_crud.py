"""Project CRUD, now that a project is a directory rather than a file.

Two themes run through these tests:

* **The destructive paths are guarded.** ``delete_project`` calls
  ``shutil.rmtree`` on a path derived from a user-supplied name, so the refusal
  test matters more than the success test.
* **Renaming and metadata edits never rewrite a step file.** Several tests hash
  ``caption_bbox.yaml`` across an operation, which is what turns the banner's
  "the app does not rewrite this file" from a hope into a promise — and is what
  lets a user keep comments in their step files.
"""
import hashlib

import pytest
import yaml

from prepare_lora_kit.pipeline import step_slugs
from prepare_lora_kit.project import project_registry, store


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _index(name):
    return yaml.safe_load(project_registry.index_path_for_name(name).read_text())


# ── create ────────────────────────────────────────────────────────────────────

def test_create_project_writes_a_folder_with_index_and_step_files(isolated_projects):
    project_registry.create_project("demo", input_dir="/data/demo")

    directory = isolated_projects / "demo"
    assert {p.name for p in directory.iterdir()} == {
        "index.yaml",
        *(f"{slug}.yaml" for slug in step_slugs()),
    }
    index = _index("demo")
    assert index["name"] == "demo"
    assert index["input_dir"] == "/data/demo"
    assert [entry["step"] for entry in index["pipeline"]] == list(step_slugs())


def test_create_project_rejects_duplicate(isolated_projects):
    project_registry.create_project("demo")

    with pytest.raises(ValueError, match="already exists"):
        project_registry.create_project("demo")


def test_create_project_rejects_an_unsafe_name(isolated_projects):
    with pytest.raises(ValueError):
        project_registry.create_project("../escape")


def test_create_project_rejects_a_blank_name(isolated_projects):
    with pytest.raises(ValueError, match="name is required"):
        project_registry.create_project("   ")


# ── rename / metadata ─────────────────────────────────────────────────────────

def test_update_project_meta_rename_moves_the_directory(isolated_projects):
    project_registry.create_project("demo", input_dir="/data/demo")
    marker = isolated_projects / "demo" / "user_notes.txt"
    marker.write_text("hand-written")

    project_registry.update_project_meta("demo", "renamed", input_dir="/data/demo")

    assert not (isolated_projects / "demo").exists()
    assert (isolated_projects / "renamed" / "user_notes.txt").read_text() == "hand-written"
    assert _index("renamed")["name"] == "renamed"


def test_rename_rewrites_only_index_yaml(isolated_projects):
    project_registry.create_project("demo")
    before = _digest(isolated_projects / "demo" / "caption_bbox.yaml")

    project_registry.update_project_meta("demo", "renamed")

    assert _digest(isolated_projects / "renamed" / "caption_bbox.yaml") == before


def test_update_project_meta_clears_dirs_when_blank(isolated_projects):
    project_registry.create_project("demo", input_dir="/data/demo", output_dir="/out")

    project_registry.update_project_meta("demo", "demo", input_dir="/data/demo")

    index = _index("demo")
    assert index["input_dir"] == "/data/demo"
    assert "output_dir" not in index


def test_rename_changing_only_case_keeps_the_project(isolated_projects):
    """On a case-insensitive filesystem this is the same directory.

    It must not read as a collision, and the displayed name must still change —
    that comes from index.yaml, not the folder.
    """
    project_registry.create_project("demo")

    project_registry.update_project_meta("demo", "Demo")

    assert project_registry.list_projects() == ["Demo"]
    assert project_registry.load("Demo").name == "Demo"


def test_update_project_meta_rejects_a_missing_project(isolated_projects):
    with pytest.raises(ValueError, match="does not exist"):
        project_registry.update_project_meta("ghost", "renamed")


def test_update_project_meta_rejects_renaming_onto_an_existing_project(isolated_projects):
    project_registry.create_project("demo")
    project_registry.create_project("taken")

    with pytest.raises(ValueError, match="already exists"):
        project_registry.update_project_meta("demo", "taken")


# ── duplicate ─────────────────────────────────────────────────────────────────

def test_duplicate_project_auto_names(isolated_projects):
    project_registry.create_project("demo")

    assert project_registry.duplicate_project("demo") == "demo_copy"
    assert project_registry.duplicate_project("demo") == "demo_copy2"
    assert _index("demo_copy2")["name"] == "demo_copy2"


def test_duplicate_preserves_step_file_bytes_including_comments(isolated_projects):
    """copytree, not a load/dump round-trip — so user comments survive."""
    project_registry.create_project("demo")
    step_file = isolated_projects / "demo" / "caption_bbox.yaml"
    step_file.write_text(step_file.read_text() + "\n# my note: this model is better\n")
    before = _digest(step_file)

    project_registry.duplicate_project("demo", "copied")

    copied = isolated_projects / "copied" / "caption_bbox.yaml"
    assert _digest(copied) == before
    assert "# my note: this model is better" in copied.read_text()


def test_duplicate_project_rejects_a_missing_project(isolated_projects):
    with pytest.raises(ValueError, match="does not exist"):
        project_registry.duplicate_project("ghost")


# ── delete ────────────────────────────────────────────────────────────────────

def test_delete_project_removes_the_whole_directory_and_is_idempotent(isolated_projects):
    project_registry.create_project("demo")

    project_registry.delete_project("demo")
    project_registry.delete_project("demo")

    assert not (isolated_projects / "demo").exists()


def test_delete_project_refuses_a_name_that_escapes_the_projects_dir(isolated_projects, tmp_path):
    """The guard that matters: a name reaches shutil.rmtree."""
    precious = tmp_path / "precious"
    precious.mkdir()
    (precious / "irreplaceable.txt").write_text("data")

    with pytest.raises(ValueError):
        project_registry.delete_project("../precious")

    assert (precious / "irreplaceable.txt").exists()


def test_delete_project_refuses_a_symlinked_project(isolated_projects, tmp_path):
    isolated_projects.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "precious"
    outside.mkdir()
    (outside / "irreplaceable.txt").write_text("data")
    try:
        (isolated_projects / "demo").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform/account")

    with pytest.raises(ValueError):
        project_registry.delete_project("demo")

    assert (outside / "irreplaceable.txt").exists()


# ── input dir ─────────────────────────────────────────────────────────────────

def test_set_project_input_dir_rewrites_only_index_yaml(isolated_projects):
    project_registry.create_project("demo")
    before = _digest(isolated_projects / "demo" / "caption_bbox.yaml")

    project_registry.set_project_input_dir("demo", "/data/new")

    assert _index("demo")["input_dir"] == "/data/new"
    assert _digest(isolated_projects / "demo" / "caption_bbox.yaml") == before


def test_set_project_input_dir_keeps_an_existing_output_dir(isolated_projects):
    project_registry.create_project("demo", output_dir="/out")

    project_registry.set_project_input_dir("demo", "/data/new")

    assert _index("demo")["output_dir"] == "/out"


def test_set_project_input_dir_creates_a_full_project_when_missing(isolated_projects):
    project_registry.set_project_input_dir("fresh", "/data/fresh")

    directory = isolated_projects / "fresh"
    assert (directory / "caption_bbox.yaml").exists()
    assert _index("fresh")["input_dir"] == "/data/fresh"


# ── load / list ───────────────────────────────────────────────────────────────

def test_load_returns_a_validated_project(isolated_projects):
    project_registry.create_project("demo", input_dir="/data/demo")

    cfg = project_registry.load("demo")

    assert cfg.name == "demo"
    assert cfg.input_dir == "/data/demo"
    assert next(step.type for step in cfg.pipeline) == "ImportStep"


def test_load_raises_value_error_for_an_unknown_project(isolated_projects):
    """cli/run.py catches exactly ValueError to offer creating the project."""
    project_registry.create_project("demo")

    with pytest.raises(ValueError, match="Unknown project 'ghost'"):
        project_registry.load("ghost")


def test_list_projects_reads_names_from_index_not_directory_names(isolated_projects):
    project_registry.create_project("foo-bar")

    assert project_registry.list_projects() == ["foo-bar"]
    assert (isolated_projects / "foo_bar").is_dir()


def test_list_projects_ignores_a_directory_without_an_index(isolated_projects):
    project_registry.create_project("demo")
    (isolated_projects / "__pycache__").mkdir()

    assert project_registry.list_projects() == ["demo"]


def test_list_projects_is_empty_before_anything_is_created(isolated_projects):
    assert project_registry.list_projects() == []


# ── seeding boundary ──────────────────────────────────────────────────────────

def test_loading_a_project_never_rewrites_any_of_its_files(isolated_projects):
    """No load-time self-rewrite may creep back in.

    The old single-file loader migrated legacy YAML *and wrote it back* on read.
    Eleven files is eleven chances for that to return, so hash all of them.
    """
    project_registry.create_project("demo", input_dir="/data/demo")
    directory = isolated_projects / "demo"
    before = {p.name: _digest(p) for p in sorted(directory.iterdir())}

    project_registry.load("demo")

    assert {p.name: _digest(p) for p in sorted(directory.iterdir())} == before


def test_a_project_missing_a_step_file_loads_on_defaults_with_a_warning(isolated_projects, capsys):
    project_registry.create_project("demo")
    (isolated_projects / "demo" / "caption_bbox.yaml").unlink()

    cfg = project_registry.load("demo")

    caption = next(s for s in cfg.pipeline if s.type == "CaptionBboxStep")
    assert caption.config.max_new_tokens == 200
    assert "caption_bbox.yaml" in capsys.readouterr().out


def test_store_and_registry_agree_on_the_project_path(isolated_projects):
    assert project_registry.config_path_for_name("foo-bar") == isolated_projects / "foo_bar"
    assert (
        project_registry.index_path_for_name("foo-bar")
        == isolated_projects / "foo_bar" / "index.yaml"
    )
    assert store.project_dir_for_name("foo-bar") == isolated_projects / "foo_bar"
