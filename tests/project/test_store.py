"""The on-disk project folder shape: ~/.prepare_lora_kit/projects/<name>/.

These tests are the contract between ``write_project_folder`` and
``read_project_folder``. They also pin the two things that make the rest of the
suite safe to run: that ``projects_dir()`` follows a monkeypatched
``paths.PROJECTS_DIR``, and that a project directory can never be resolved
outside the projects root.
"""
import pytest
import yaml

from prepare_lora_kit import paths
from prepare_lora_kit.pipeline import step_slugs
from prepare_lora_kit.project import store
from prepare_lora_kit.project.project_registry import default_project_data

EXPECTED_FILES = {"index.yaml", *(f"{slug}.yaml" for slug in step_slugs())}


# ── round-trip ────────────────────────────────────────────────────────────────

def test_write_then_read_round_trips_the_flat_dict(isolated_projects):
    data = default_project_data("demo", input_dir="/data/demo")
    directory = isolated_projects / "demo"

    store.write_project_folder(directory, data)
    restored, notes = store.read_project_folder(directory)

    assert restored == data
    assert notes == []


def test_write_creates_index_and_one_file_per_step(isolated_projects):
    directory = isolated_projects / "demo"

    store.write_project_folder(directory, default_project_data("demo"))

    assert {p.name for p in directory.iterdir()} == EXPECTED_FILES


def test_step_file_is_flat_with_no_type_key(isolated_projects):
    directory = isolated_projects / "demo"
    store.write_project_folder(directory, default_project_data("demo"))

    parsed = yaml.safe_load((directory / "caption_bbox.yaml").read_text())

    assert "type" not in parsed
    assert [entry["id"] for entry in parsed["substeps"]] == [
        "annotate_regions",
        "caption_images",
        "validate_captions",
    ]
    # Config fields are top-level siblings of substeps, not nested under a key.
    assert parsed["vram_tier"] == "auto"
    assert parsed["max_new_tokens"] == 200


def test_step_file_never_contains_a_top_level_enabled(isolated_projects):
    """``index.yaml`` owns ``enabled``; a step-file copy would shadow it.

    ``ProjectConfig.from_data`` pops ``enabled`` off each merged step dict, so a
    stray ``enabled:`` inside a step file would silently override the index.
    """
    directory = isolated_projects / "demo"
    data = default_project_data("demo")
    data["pipeline"][3]["enabled"] = False

    store.write_project_folder(directory, data)

    for slug in step_slugs():
        parsed = yaml.safe_load((directory / f"{slug}.yaml").read_text())
        assert "enabled" not in parsed, slug


def test_index_lists_every_step_enabled_by_default(isolated_projects):
    """Including the three optional ones.

    ``enabled`` is pipeline membership; ``optional`` is only the UI's default
    checkbox state. If optional steps were written as disabled they would vanish
    from the UI payload entirely and could never be switched back on there.
    """
    directory = isolated_projects / "demo"
    store.write_project_folder(directory, default_project_data("demo"))

    index = yaml.safe_load((directory / "index.yaml").read_text())

    assert index["pipeline"] == [
        {"step": slug, "enabled": True} for slug in step_slugs()
    ]


def test_disabled_step_round_trips_through_the_index(isolated_projects):
    directory = isolated_projects / "demo"
    data = default_project_data("demo")
    data["pipeline"][3]["enabled"] = False

    store.write_project_folder(directory, data)
    restored, _ = store.read_project_folder(directory)

    index = yaml.safe_load((directory / "index.yaml").read_text())
    assert {"step": "upscale", "enabled": False} in index["pipeline"]
    assert restored["pipeline"][3]["enabled"] is False
    assert (directory / "upscale.yaml").exists()


# ── reader tolerance ──────────────────────────────────────────────────────────

def test_reader_ignores_a_step_file_not_listed_in_the_index(isolated_projects):
    directory = isolated_projects / "demo"
    data = default_project_data("demo")
    data["pipeline"] = [step for step in data["pipeline"] if step["type"] != "UpscaleStep"]
    store.write_project_folder(directory, data)
    (directory / "upscale.yaml").write_text("upscale_target: 4096\n")

    restored, notes = store.read_project_folder(directory)

    assert [step["type"] for step in restored["pipeline"]] == [
        step["type"] for step in data["pipeline"]
    ]
    assert notes == []


def test_reader_ignores_an_unknown_yaml_file_in_the_folder(isolated_projects):
    directory = isolated_projects / "demo"
    store.write_project_folder(directory, default_project_data("demo"))
    (directory / "notes.yaml").write_text("anything: goes\n")
    (directory / "upscale.yaml.bak").write_text("upscale_target: 4096\n")

    restored, notes = store.read_project_folder(directory)

    assert len(restored["pipeline"]) == len(step_slugs())
    assert notes == []


def test_reader_defaults_a_listed_step_whose_file_is_missing(isolated_projects):
    directory = isolated_projects / "demo"
    store.write_project_folder(directory, default_project_data("demo"))
    (directory / "caption_bbox.yaml").unlink()

    restored, notes = store.read_project_folder(directory)

    caption = next(s for s in restored["pipeline"] if s["type"] == "CaptionBboxStep")
    # Enabled is the default, so it is left off the flat dict entirely — only a
    # disabled step carries the key. That keeps the round-trip exact against
    # _default_pipeline(), which has no `enabled` key of its own.
    assert caption == {"type": "CaptionBboxStep"}
    assert any("caption_bbox.yaml" in note for note in notes)


def test_reader_rejects_an_unknown_slug_and_lists_the_known_ones(isolated_projects):
    directory = isolated_projects / "demo"
    store.write_project_folder(directory, default_project_data("demo"))
    index = yaml.safe_load((directory / "index.yaml").read_text())
    index["pipeline"].append({"step": "captions", "enabled": True})
    (directory / "index.yaml").write_text(yaml.safe_dump(index, sort_keys=False))

    with pytest.raises(ValueError) as excinfo:
        store.read_project_folder(directory)

    message = str(excinfo.value)
    assert "captions" in message
    assert "caption_bbox" in message


def test_reader_rejects_a_project_without_an_index(isolated_projects):
    directory = isolated_projects / "demo"
    directory.mkdir(parents=True)

    with pytest.raises(ValueError, match=r"index\.yaml"):
        store.read_project_folder(directory)


def test_index_only_is_a_valid_minimal_project(isolated_projects):
    directory = isolated_projects / "demo"
    directory.mkdir(parents=True)
    (directory / "index.yaml").write_text(
        "name: demo\npipeline:\n  - {step: import, enabled: true}\n"
    )

    restored, notes = store.read_project_folder(directory)

    assert restored["name"] == "demo"
    assert restored["pipeline"] == [{"type": "ImportStep"}]
    assert any("import.yaml" in note for note in notes)


# ── the test seam itself ──────────────────────────────────────────────────────

def test_projects_dir_follows_a_monkeypatched_paths_attribute(tmp_path, monkeypatch):
    """Pins the seam the whole suite's safety rests on.

    ``store`` must read ``paths.PROJECTS_DIR`` through the module attribute. If
    someone converts it to a from-import it binds at import time, the autouse
    ``isolated_projects`` fixture stops working, and every project test starts
    writing into the developer's real home directory. This test fails first.
    """
    elsewhere = tmp_path / "elsewhere"
    monkeypatch.setattr(paths, "PROJECTS_DIR", elsewhere)

    assert store.projects_dir() == elsewhere
    assert store.project_dir_for_name("demo") == elsewhere / "demo"


# ── name validation and the rmtree guard ──────────────────────────────────────

@pytest.mark.parametrize(
    "name",
    ["..", ".", "a/b", "a\\b", "", "   ", ".hidden", "C:evil", "a:b", "x\ty"],
)
def test_dir_name_for_rejects_unsafe_names(name):
    with pytest.raises(ValueError):
        store.dir_name_for(name)


def test_dir_name_for_maps_hyphens_to_underscores():
    assert store.dir_name_for("foo-bar") == "foo_bar"
    assert store.dir_name_for("  spaced  ") == "spaced"


def test_assert_inside_projects_dir_accepts_a_direct_child(isolated_projects):
    target = isolated_projects / "demo"

    assert store.assert_inside_projects_dir(target) == target.resolve()


def test_assert_inside_projects_dir_rejects_the_root_itself(isolated_projects):
    with pytest.raises(ValueError):
        store.assert_inside_projects_dir(isolated_projects)


def test_assert_inside_projects_dir_rejects_an_outside_path(isolated_projects, tmp_path):
    with pytest.raises(ValueError):
        store.assert_inside_projects_dir(tmp_path / "not_a_project")


def test_assert_inside_projects_dir_rejects_a_nested_grandchild(isolated_projects):
    with pytest.raises(ValueError):
        store.assert_inside_projects_dir(isolated_projects / "demo" / "nested")


def test_assert_inside_projects_dir_rejects_a_symlink(isolated_projects, tmp_path):
    isolated_projects.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "precious"
    outside.mkdir()
    link = isolated_projects / "demo"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform/account")

    with pytest.raises(ValueError):
        store.assert_inside_projects_dir(link)


# ── listing ───────────────────────────────────────────────────────────────────

def test_list_project_names_reads_names_from_the_index(isolated_projects):
    store.write_project_folder(
        store.project_dir_for_name("foo-bar"), default_project_data("foo-bar")
    )

    assert store.list_project_names() == ["foo-bar"]
    assert (isolated_projects / "foo_bar").is_dir()


def test_list_project_names_skips_directories_without_an_index(isolated_projects):
    store.write_project_folder(
        store.project_dir_for_name("real"), default_project_data("real")
    )
    (isolated_projects / "__pycache__").mkdir()
    (isolated_projects / "half_copied").mkdir()

    assert store.list_project_names() == ["real"]


def test_list_project_names_skips_dot_prefixed_directories(isolated_projects):
    """In-flight ``.<name>.plk_tmp`` folders contain a valid index."""
    store.write_project_folder(
        store.project_dir_for_name("real"), default_project_data("real")
    )
    partial = isolated_projects / ".real.plk_tmp"
    partial.mkdir()
    (partial / "index.yaml").write_text("name: real\npipeline: []\n")

    assert store.list_project_names() == ["real"]


def test_list_project_names_tolerates_a_missing_projects_dir(isolated_projects):
    assert not isolated_projects.exists()
    assert store.list_project_names() == []


# ── durability ────────────────────────────────────────────────────────────────

def test_write_is_atomic_and_leaves_no_temp_folder(isolated_projects):
    directory = store.project_dir_for_name("demo")

    store.write_project_folder(directory, default_project_data("demo"))

    assert [p.name for p in isolated_projects.iterdir()] == ["demo"]


def test_rewriting_an_existing_project_replaces_it_cleanly(isolated_projects):
    directory = store.project_dir_for_name("demo")
    store.write_project_folder(directory, default_project_data("demo"))

    store.write_project_folder(directory, default_project_data("demo", input_dir="/x"))

    assert {p.name for p in directory.iterdir()} == EXPECTED_FILES
    assert [p.name for p in isolated_projects.iterdir()] == ["demo"]


def test_files_carry_a_comment_banner(isolated_projects):
    directory = store.project_dir_for_name("demo")
    store.write_project_folder(directory, default_project_data("demo"))

    index_text = (directory / "index.yaml").read_text()
    step_text = (directory / "caption_bbox.yaml").read_text()

    assert index_text.startswith("#")
    assert "caption_bbox" in index_text  # canonical order line
    assert step_text.startswith("#")
    assert "CaptionBboxStep" in step_text
    assert "annotate_regions" in step_text


def test_substeps_and_buckets_are_written_in_inline_flow_style(isolated_projects):
    """The readability point of the split: one line per entry, not two."""
    directory = store.project_dir_for_name("demo")
    store.write_project_folder(directory, default_project_data("demo"))

    assert "- {id: annotate_regions, enabled: true}" in (
        directory / "caption_bbox.yaml"
    ).read_text()
    assert "- {step: import, enabled: true}" in (directory / "index.yaml").read_text()

    buckets = (directory / "bucket_pools_check.yaml").read_text()
    assert "- [1024, 1024]" in buckets
