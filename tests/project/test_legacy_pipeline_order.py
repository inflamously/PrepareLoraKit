"""Projects written before a canonical-order change must keep working.

``ProjectConfig._validate_pipeline`` rejects a ``pipeline:`` list whose canonical
orders are not strictly increasing, and that rejection is deliberate — it is what
stops ``index.yaml`` from lying about what will run. It is also what breaks every
project already on disk the moment *we* move a step.

So the repair is narrow on purpose, and these tests pin both halves of that: a
list valid under a previously-shipped layout is relocated and the file rewritten,
and anything else is still rejected exactly as before.

Most tests monkeypatch ``LEGACY_SLUG_ORDERS`` to a synthetic layout rather than
using the real one. The real entry is a no-op in the release that introduces it
(the "old" order still *is* the current order), so a test written against it
would silently stop exercising the relocation.
"""
import pytest
import yaml

from prepare_lora_kit.pipeline import step_slugs
from prepare_lora_kit.project import legacy_order, store
from prepare_lora_kit.project.base import ProjectConfig
from prepare_lora_kit.project.project_registry import default_project_data, load

# Valid under prerequisites (export needs only import), invalid under the current
# canonical order — so it can only load if the relocation runs.
SYNTHETIC_LEGACY = (
    *(slug for slug in step_slugs() if slug not in ("bucket_pools_check", "export")),
    "export",
    "bucket_pools_check",
)


@pytest.fixture
def legacy_layout(monkeypatch):
    monkeypatch.setattr(legacy_order, "LEGACY_SLUG_ORDERS", (SYNTHETIC_LEGACY,))
    return SYNTHETIC_LEGACY


def _write_project(directory, **overrides):
    store.write_project_folder(directory, default_project_data("demo", **overrides))
    return directory


def _rewrite_index_order(directory, slugs, *, disabled=()):
    """Rewrite index.yaml's pipeline in ``slugs`` order, as an older release would."""
    data = store.read_index(directory)
    data["pipeline"] = [{"step": slug, "enabled": slug not in disabled} for slug in slugs]
    store.write_index(directory, data)


def _index_slugs(directory):
    entry_list = store.read_index(directory)["pipeline"]
    return [entry["step"] for entry in entry_list]


def _snapshot(directory):
    return {path.name: path.read_bytes() for path in sorted(directory.iterdir())}


# ── the repair ────────────────────────────────────────────────────────────────

def test_a_legacy_index_still_loads_in_canonical_order(isolated_projects, legacy_layout):
    directory = _write_project(isolated_projects / "demo")
    _rewrite_index_order(directory, legacy_layout)

    project = load("demo")

    assert [step.type for step in project.pipeline] == [
        store.step_type_for_slug(slug) for slug in step_slugs()
    ]


def test_a_legacy_index_keeps_every_tuned_step_setting(isolated_projects, legacy_layout):
    """The point of the narrow repair: index.yaml moves, <step>.yaml does not."""
    directory = _write_project(isolated_projects / "demo")
    (directory / "upscale.yaml").write_text("upscale_target: 4096\n", encoding="utf-8")
    _rewrite_index_order(directory, legacy_layout)

    project = load("demo")

    upscale = next(step for step in project.pipeline if step.type == "UpscaleStep")
    assert upscale.config.upscale_target == 4096


def test_the_repair_rewrites_only_index_yaml(isolated_projects, legacy_layout):
    directory = _write_project(isolated_projects / "demo")
    _rewrite_index_order(directory, legacy_layout)
    before = _snapshot(directory)

    load("demo")

    after = _snapshot(directory)
    changed = [name for name in before if before[name] != after[name]]
    assert changed == ["index.yaml"]
    assert _index_slugs(directory) == list(step_slugs())


def test_the_repair_keeps_the_index_entries_inline(isolated_projects, legacy_layout):
    """``- {step: import, enabled: true}`` is the shape the rest of the suite pins."""
    directory = _write_project(isolated_projects / "demo")
    _rewrite_index_order(directory, legacy_layout)

    load("demo")

    assert "- {step: import, enabled: true}" in (directory / "index.yaml").read_text(
        encoding="utf-8"
    )


def test_the_repair_preserves_the_index_mtime(isolated_projects, legacy_layout):
    """The library grid sorts on this — a migration must not reshuffle it."""
    directory = _write_project(isolated_projects / "demo")
    _rewrite_index_order(directory, legacy_layout)
    index_file = directory / store.INDEX_FILENAME
    before = index_file.stat().st_mtime_ns

    load("demo")

    assert index_file.stat().st_mtime_ns == before


def test_a_parked_step_stays_parked_across_the_move(isolated_projects, legacy_layout):
    directory = _write_project(isolated_projects / "demo")
    _rewrite_index_order(directory, legacy_layout, disabled=("export",))

    project = load("demo")

    assert "ExportStep" in project.disabled_types
    entries = store.read_index(directory)["pipeline"]
    assert {e["step"]: e["enabled"] for e in entries}["export"] is False


def test_the_repair_is_idempotent(isolated_projects, legacy_layout):
    directory = _write_project(isolated_projects / "demo")
    _rewrite_index_order(directory, legacy_layout)

    load("demo")
    after_first = _snapshot(directory)
    load("demo")

    assert _snapshot(directory) == after_first
    assert store.repair_index_order(directory) is None


def test_a_current_project_is_never_touched(isolated_projects):
    directory = _write_project(isolated_projects / "demo")
    before = _snapshot(directory)

    load("demo")

    assert _snapshot(directory) == before
    assert store.repair_index_order(directory) is None


# ── what must still be rejected ───────────────────────────────────────────────

def test_a_hand_shuffled_index_still_raises_and_is_not_rewritten(isolated_projects):
    """A user who reordered the file on purpose gets told, not silently corrected."""
    directory = _write_project(isolated_projects / "demo")
    shuffled = [
        slug for slug in step_slugs() if slug not in ("quality_gate", "curate")
    ]
    shuffled.insert(1, "curate")
    shuffled.insert(2, "quality_gate")
    _rewrite_index_order(directory, shuffled)
    before = _snapshot(directory)

    with pytest.raises(ValueError, match=r"out of order|requires"):
        load("demo")

    assert _snapshot(directory) == before


def test_an_unknown_slug_still_raises(isolated_projects, legacy_layout):
    directory = _write_project(isolated_projects / "demo")
    _rewrite_index_order(directory, (*legacy_layout, "not_a_step"))

    with pytest.raises(ValueError, match="Unknown step"):
        load("demo")


def test_a_duplicated_slug_still_raises(isolated_projects, legacy_layout):
    """Duplicated in place, so only the duplicate — not the order — can be the cause."""
    directory = _write_project(isolated_projects / "demo")
    doubled = list(step_slugs())
    doubled.insert(doubled.index("curate"), "curate")
    _rewrite_index_order(directory, doubled)

    with pytest.raises(ValueError, match="Duplicate step type"):
        load("demo")


# ── layering ──────────────────────────────────────────────────────────────────

def test_from_dir_repairs_in_memory_without_touching_disk(isolated_projects, legacy_layout):
    """``ProjectConfig.from_dir`` must stay a pure read — see test_seeding.py."""
    directory = _write_project(isolated_projects / "demo")
    _rewrite_index_order(directory, legacy_layout)
    before = _snapshot(directory)

    project = ProjectConfig.from_dir(directory)

    assert [step.type for step in project.pipeline][-2:] == [
        "BucketPoolsCheckStep",
        "ExportStep",
    ]
    assert _snapshot(directory) == before


def test_load_survives_an_unwritable_index(isolated_projects, legacy_layout, monkeypatch):
    """A read-only project folder must degrade to an in-memory fix, not an error tile."""
    directory = _write_project(isolated_projects / "demo")
    _rewrite_index_order(directory, legacy_layout)

    def _refuse(*_args, **_kwargs):
        raise OSError("read-only file system")

    monkeypatch.setattr(store, "write_index", _refuse)

    project = load("demo")

    assert [step.type for step in project.pipeline][-2:] == [
        "BucketPoolsCheckStep",
        "ExportStep",
    ]


# ── the relocator itself ──────────────────────────────────────────────────────

def test_relocate_is_a_no_op_for_canonical_input(legacy_layout):
    entries = [(slug, True) for slug in step_slugs()]

    relocated, note = legacy_order.relocate_legacy_entries(entries)

    assert relocated == entries
    assert note is None


def test_relocate_names_the_step_that_moved(legacy_layout):
    entries = [(slug, True) for slug in legacy_layout]

    relocated, note = legacy_order.relocate_legacy_entries(entries)

    assert [slug for slug, _ in relocated] == list(step_slugs())
    assert "bucket_pools_check" in note


def test_relocate_declines_a_layout_it_does_not_recognise(legacy_layout):
    entries = [(slug, True) for slug in reversed(step_slugs())]

    relocated, note = legacy_order.relocate_legacy_entries(entries)

    assert relocated == entries
    assert note is None


def test_relocate_handles_a_subset_of_steps(legacy_layout):
    """Optional steps are routinely absent; a partial list must still relocate."""
    entries = [(slug, True) for slug in legacy_layout if slug != "upscale"]

    relocated, note = legacy_order.relocate_legacy_entries(entries)

    assert [slug for slug, _ in relocated] == [s for s in step_slugs() if s != "upscale"]
    assert note is not None


def test_the_shipped_legacy_orders_are_all_real_layouts():
    """A typo in LEGACY_SLUG_ORDERS would silently disable the migration."""
    for layout in legacy_order.LEGACY_SLUG_ORDERS:
        assert sorted(layout) == sorted(step_slugs()), f"{layout} is not a full pipeline"


def test_the_documented_index_example_parses_as_canonical(isolated_projects):
    """Guards the note text's claim that nothing but ordering changes."""
    directory = _write_project(isolated_projects / "demo")
    raw = yaml.safe_load((directory / store.INDEX_FILENAME).read_text(encoding="utf-8"))

    assert [entry["step"] for entry in raw["pipeline"]] == list(step_slugs())
