"""Developer-only mock fixture support for UI step smoke runs."""
from __future__ import annotations

from pathlib import Path

from prepare_lora_kit.pipeline import step_types
from prepare_lora_kit.project.pipeline.substeps import substep_ids_for
from prepare_lora_kit.utils.state import RunState
from prepare_lora_kit_ui.e2e.assets import (
    prepare_root,
    reset_dir,
    seed_working_dataset,
    write_captions,
    write_source_images,
)
from prepare_lora_kit_ui.e2e.models import MockUiFixture
from prepare_lora_kit_ui.e2e.project import mock_project
from prepare_lora_kit_ui.e2e.steps import resolve_mock_steps
from prepare_lora_kit_ui.paths import PROJECT_ROOT


def create_mock_ui_fixture(
        raw_step: str,
        root: Path | None = None,
        curate_coverage: str = "auto",
) -> MockUiFixture:
    selected_steps = resolve_mock_steps(raw_step)
    curate_coverage = curate_coverage.lower().strip()
    if curate_coverage not in {"auto", "pca", "umap"}:
        raise ValueError("Mock curate coverage must be one of: auto, pca, umap")
    root = (root or PROJECT_ROOT / "outputs" / "_ui_mock").expanduser().resolve()
    prepare_root(root)
    input_dir = root / "input"
    output_dir = root / "run"
    working_dir = output_dir / "dataset"

    reset_dir(input_dir)
    reset_dir(output_dir)
    write_source_images(
        input_dir,
        include_pca_set=curate_coverage == "pca",
        include_umap_set=curate_coverage == "umap",
    )
    seed_working_dataset(input_dir, working_dir, selected_steps)

    project = mock_project(input_dir)
    seed_state(output_dir, selected_steps)
    if needs_seeded_captions(selected_steps):
        write_captions(working_dir)

    return MockUiFixture(
        root=root,
        input_dir=input_dir,
        output_dir=output_dir,
        project=project,
        selected_steps=selected_steps,
        curate_coverage=curate_coverage,
    )


def seed_state(output_dir: Path, selected_steps: list[str]) -> None:
    """Pretend every step before the one under test already ran.

    Substeps are marked individually so the fixture's records have the same shape
    a real run leaves; a record with no substeps map reads as a pre-substep
    legacy manifest. Deliberately *no* ``outcome``: these steps did not execute
    and left no report, and claiming they did would earn them a ``stale`` badge
    from the report cross-check.
    """
    ordered_steps = list(step_types())
    first_index = min(ordered_steps.index(step) for step in selected_steps)
    state = RunState(output_dir)
    for step_type in ordered_steps[:first_index]:
        substeps = substep_ids_for(step_type)
        for substep_id in substeps:
            state.mark_substep_done(step_type, substep_id)
        state.mark_done(
            step_type, {"enabled_substeps": substeps, "mock_fixture": True}
        )


def needs_seeded_captions(selected_steps: list[str]) -> bool:
    ordered_steps = list(step_types())
    first_index = min(ordered_steps.index(step) for step in selected_steps)
    caption_index = ordered_steps.index("CaptionBboxStep")
    return first_index > caption_index
