"""Developer-only mock fixture support for UI step smoke runs."""
from __future__ import annotations

from pathlib import Path

from prepare_lora_kit_pipeline.configuration import STEP_TYPE_MAP
from prepare_lora_kit.utils.state import RunState
from ..paths import PROJECT_ROOT
from .assets import (
    prepare_root,
    reset_dir,
    seed_working_dataset,
    write_captions,
    write_source_images,
)
from .models import MockUiFixture
from .project import mock_project
from .steps import resolve_mock_steps


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
    first_index = min(list(STEP_TYPE_MAP).index(step) for step in selected_steps)
    state = RunState(output_dir)
    for step_type in list(STEP_TYPE_MAP)[:first_index]:
        state.mark_done(step_type, {"mock_fixture": True})


def needs_seeded_captions(selected_steps: list[str]) -> bool:
    first_index = min(list(STEP_TYPE_MAP).index(step) for step in selected_steps)
    caption_index = list(STEP_TYPE_MAP).index("CaptionStep")
    return first_index > caption_index
