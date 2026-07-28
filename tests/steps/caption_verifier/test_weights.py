"""Tests for the caption verifier's weight accounting.

Nothing here downloads or loads a model. What is under test is the arithmetic a
user reads while a 9B checkpoint spends ten minutes landing: that the total is
the real size of the files on disk, that the loaded figure tracks the load's own
tqdm bars, and that it says nothing at all rather than guessing.

Checkpoints are built as directory trees under ``tmp_path`` — the layout *is*
the input, so faking the scan would test nothing.
"""
from __future__ import annotations

import json
import types

import pytest

from prepare_lora_kit.steps.caption_verifier import weights

MB = 1024 ** 2


def _bar(desc: str, n: int, total: int | None):
    return types.SimpleNamespace(desc=desc, n=n, total=total, unit="it")


def _checkpoint(root, components: dict[str, dict[str, int]]):
    """Write a diffusers-style repo. ``{"vae": {"model.safetensors": 200}}``."""
    index = {"_class_name": "FakePipeline", "_diffusers_version": "0.38.0"}
    for name, files in components.items():
        index[name] = ["diffusers", "FakeModel"]
        folder = root / name
        folder.mkdir(parents=True, exist_ok=True)
        for filename, size in files.items():
            (folder / filename).write_bytes(b"\0" * size)
    (root / "model_index.json").write_text(json.dumps(index), encoding="utf-8")
    return root


# --- measuring the checkpoint ----------------------------------------------

def test_components_are_sized_from_the_files_on_disk(tmp_path):
    """Not from catalog parameter counts, which quantization makes wrong."""
    root = _checkpoint(tmp_path / "repo", {
        "text_encoder": {"model.safetensors": 3 * MB},
        "transformer": {"model.safetensors": 6 * MB},
        "vae": {"diffusion_pytorch_model.safetensors": 1 * MB},
    })

    components = weights.read_components(str(root))

    assert [(c.name, c.size) for c in components] == [
        ("text_encoder", 3 * MB), ("transformer", 6 * MB), ("vae", 1 * MB),
    ]


def test_components_keep_the_order_the_pipeline_loads_them_in(tmp_path):
    """Position is how a completed-component count becomes bytes."""
    root = _checkpoint(tmp_path / "repo", {
        "vae": {"model.safetensors": 1 * MB},
        "tokenizer": {},
        "transformer": {"model.safetensors": 8 * MB},
    })

    components = weights.read_components(str(root))

    assert [c.name for c in components] == ["vae", "tokenizer", "transformer"]
    assert components[1].size == 0  # a tokenizer is a bar step with no weights


def test_legacy_bin_weights_are_not_counted_beside_safetensors(tmp_path):
    """A repo shipping both formats holds the same weights twice."""
    root = _checkpoint(tmp_path / "repo", {
        "unet": {
            "diffusion_pytorch_model.safetensors": 5 * MB,
            "diffusion_pytorch_model.bin": 5 * MB,
        },
    })

    components = weights.read_components(str(root))

    assert components[0].size == 5 * MB


def test_a_bin_only_component_is_still_counted(tmp_path):
    root = _checkpoint(tmp_path / "repo", {"unet": {"pytorch_model.bin": 4 * MB}})

    assert weights.read_components(str(root))[0].size == 4 * MB


def test_fp16_variants_are_not_counted_beside_the_plain_files(tmp_path):
    """Both are cached when a user has pulled the repo twice; one is loaded."""
    root = _checkpoint(tmp_path / "repo", {
        "unet": {
            "diffusion_pytorch_model.safetensors": 10 * MB,
            "diffusion_pytorch_model.fp16.safetensors": 5 * MB,
        },
    })

    assert weights.read_components(str(root))[0].size == 10 * MB


def test_shards_of_one_component_are_summed(tmp_path):
    root = _checkpoint(tmp_path / "repo", {
        "transformer": {
            "diffusion_pytorch_model-00001-of-00002.safetensors": 4 * MB,
            "diffusion_pytorch_model-00002-of-00002.safetensors": 3 * MB,
        },
    })

    assert weights.read_components(str(root))[0].size == 7 * MB


def test_skipped_components_are_left_out_entirely(tmp_path):
    """The loader passes safety_checker=None, so those bytes are never read."""
    root = _checkpoint(tmp_path / "repo", {
        "safety_checker": {"model.safetensors": 2 * MB},
        "unet": {"model.safetensors": 5 * MB},
    })

    components = weights.read_components(str(root), skip=("safety_checker",))

    assert [c.name for c in components] == ["unet"]


def test_a_checkpoint_that_is_not_there_yet_measures_as_nothing(tmp_path):
    assert weights.read_components(str(tmp_path / "missing")) is None


def test_a_single_file_model_id_is_not_a_pipeline_to_measure():
    assert weights.read_components("some/repo::flux.safetensors") is None
    assert weights.read_components("/models/sdxl.safetensors") is None


def test_a_repo_with_no_weight_files_reports_nothing(tmp_path):
    """A total of zero would render as a load that can never finish."""
    root = _checkpoint(tmp_path / "repo", {"tokenizer": {"vocab.json": 12}})

    assert weights.read_components(str(root)) is None


# --- tracking the load ------------------------------------------------------

def _progress(tmp_path, **kwargs):
    root = _checkpoint(tmp_path / "repo", {
        "vae": {"model.safetensors": 1 * MB},
        "text_encoder": {
            "model-00001-of-00002.safetensors": 2 * MB,
            "model-00002-of-00002.safetensors": 2 * MB,
        },
        "transformer": {"model.safetensors": 5 * MB},
    })
    return weights.WeightProgress(str(root), **kwargs)


def test_nothing_is_loaded_before_the_first_bar(tmp_path):
    assert _progress(tmp_path).snapshot() == (0, 10 * MB)


def test_a_finished_component_is_credited_its_own_size(tmp_path):
    """Counting components would call the VAE a third of a 9 GB load."""
    progress = _progress(tmp_path)

    progress.note(_bar("Loading pipeline components...", n=1, total=3))

    assert progress.snapshot() == (1 * MB, 10 * MB)


def test_shards_move_the_figure_inside_the_component_in_flight(tmp_path):
    progress = _progress(tmp_path)
    progress.note(_bar("Loading pipeline components...", n=1, total=3))

    progress.note(_bar("Loading checkpoint shards", n=1, total=2))

    # The VAE, plus half of the text encoder now being read.
    assert progress.snapshot() == (1 * MB + 2 * MB, 10 * MB)


def test_a_shard_bar_never_leaks_into_the_next_component(tmp_path):
    """Its bar has closed; its fraction now belongs to nothing."""
    progress = _progress(tmp_path)
    progress.note(_bar("Loading pipeline components...", n=1, total=3))
    progress.note(_bar("Loading checkpoint shards", n=2, total=2))

    progress.note(_bar("Loading pipeline components...", n=2, total=3))

    assert progress.snapshot() == (1 * MB + 4 * MB, 10 * MB)


def test_the_whole_checkpoint_is_credited_once_the_last_component_lands(tmp_path):
    progress = _progress(tmp_path)

    progress.note(_bar("Loading pipeline components...", n=3, total=3))

    assert progress.snapshot() == (10 * MB, 10 * MB)


def test_the_figure_never_runs_backwards(tmp_path):
    """A retreating progress line reads as a fault rather than a re-scan."""
    progress = _progress(tmp_path)
    progress.note(_bar("Loading pipeline components...", n=2, total=3))
    assert progress.snapshot() == (5 * MB, 10 * MB)

    progress.note(_bar("Loading pipeline components...", n=0, total=3))

    assert progress.snapshot() == (5 * MB, 10 * MB)


def test_a_bar_counting_something_else_is_scaled_rather_than_trusted(tmp_path):
    """A diffusers release that hands init_dict a different set of components."""
    progress = _progress(tmp_path)

    progress.note(_bar("Loading pipeline components...", n=3, total=6))

    # Half of six components read as half of our three, not as all of them.
    assert progress.snapshot() == (1 * MB, 10 * MB)


def test_an_unmeasurable_checkpoint_reports_nothing(tmp_path):
    progress = weights.WeightProgress(str(tmp_path / "missing"))

    progress.note(_bar("Loading pipeline components...", n=1, total=3))

    assert progress.snapshot() is None


def test_the_checkpoint_is_re_read_until_it_is_there(tmp_path):
    """On a first run the files arrive part way through the load."""
    root = tmp_path / "repo"
    progress = weights.WeightProgress(str(root))
    assert progress.snapshot() is None

    _checkpoint(root, {"unet": {"model.safetensors": 4 * MB}})

    assert progress.snapshot() == (0, 4 * MB)


def test_a_bar_with_junk_totals_is_ignored(tmp_path):
    """tqdm bars come from three libraries; none of them owe us a number."""
    progress = _progress(tmp_path)

    progress.note(_bar("Loading checkpoint shards", n=1, total=None))
    progress.note(_bar("Fetching 6 files", n=4, total=6))

    assert progress.snapshot() == (0, 10 * MB)


@pytest.mark.parametrize("desc", [
    "Loading checkpoint shards",
    "Loading state_dict",
])
def test_both_per_file_bars_drive_the_component_in_flight(tmp_path, desc):
    """diffusers uses one name for sharded loads and another for transformers."""
    progress = _progress(tmp_path)
    progress.note(_bar("Loading pipeline components...", n=1, total=3))

    progress.note(_bar(desc, n=1, total=2))

    assert progress.snapshot() == (3 * MB, 10 * MB)
