"""Keep docs/project-config.md honest.

The thing we escaped by deleting ``configs/projects/example.yaml`` was an example
nothing executed, which had drifted from the real defaults without anyone
noticing. A prose doc has exactly the same failure mode, so the YAML blocks in it
are parsed and checked against the code they describe.
"""
import dataclasses
import re
from pathlib import Path

import pytest
import yaml

from prepare_lora_kit.paths import PROJECT_ROOT
from prepare_lora_kit.pipeline import step_config_class, step_slugs, step_type_for_slug
from prepare_lora_kit.project.pipeline.substeps import substep_ids_for

DOC = PROJECT_ROOT / "docs" / "project-config.md"


def _yaml_blocks() -> dict[str, dict]:
    """Every ```yaml block, keyed by the `# <filename>` comment on its first line."""
    blocks = {}
    for body in re.findall(r"```yaml\n(.*?)```", DOC.read_text(encoding="utf-8"), re.S):
        first = body.splitlines()[0].strip()
        name = first[1:].strip() if first.startswith("#") else "index.yaml"
        blocks[name] = yaml.safe_load(body)
    return blocks


def test_the_doc_exists_and_has_yaml_examples():
    assert DOC.exists()
    assert {"index.yaml", "caption_bbox.yaml", "quality_gate.yaml"} <= _yaml_blocks().keys()


def test_documented_index_lists_every_step_in_canonical_order():
    index = _yaml_blocks()["index.yaml"]

    assert [entry["step"] for entry in index["pipeline"]] == list(step_slugs())


@pytest.mark.parametrize("filename", ["caption_bbox.yaml", "quality_gate.yaml"])
def test_documented_step_files_only_use_real_fields(filename):
    block = _yaml_blocks()[filename]
    step_type = step_type_for_slug(filename.removesuffix(".yaml"))
    known = {f.name for f in dataclasses.fields(step_config_class(step_type))}

    for key in block:
        if key == "substeps":
            continue
        assert key in known, f"{filename} documents '{key}', which {step_type} has no field for"


@pytest.mark.parametrize("filename", ["caption_bbox.yaml", "quality_gate.yaml"])
def test_documented_substeps_are_real(filename):
    block = _yaml_blocks()[filename]
    step_type = step_type_for_slug(filename.removesuffix(".yaml"))
    known = set(substep_ids_for(step_type))

    for entry in block.get("substeps", []):
        assert entry["id"] in known, f"{filename} documents unknown substep '{entry['id']}'"


def test_documented_slug_table_matches_the_code():
    """The slug -> step type table is the doc's most load-bearing content."""
    text = DOC.read_text(encoding="utf-8")

    for slug in step_slugs():
        step_type = step_type_for_slug(slug)
        assert f"`{slug}.yaml` | `{step_type}`" in text, f"{slug} row missing or wrong"


def test_no_doc_still_points_at_the_old_single_file_layout():
    stale = [
        path
        for path in [
            PROJECT_ROOT / "README.md",
            PROJECT_ROOT / "AGENTS.md",
            DOC,
            PROJECT_ROOT / "docs" / "settings.md",
        ]
        if "configs/projects" in path.read_text(encoding="utf-8")
    ]

    assert not stale, f"still document the pre-split location: {[p.name for p in stale]}"
