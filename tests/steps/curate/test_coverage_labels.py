"""Unit tests for coverage-plot point labels."""
from pathlib import Path

from prepare_lora_kit.steps.curate.coverage import _LABEL_MAX, _point_labels


def test_colliding_filenames_get_parent_dir_prefix():
    paths = [Path("a/img.png"), Path("b/img.png")]
    assert _point_labels(paths) == ["a/img.png", "b/img.png"]


def test_unique_filename_keeps_bare_name():
    paths = [Path("a/cat.png"), Path("b/dog.png")]
    assert _point_labels(paths) == ["cat.png", "dog.png"]


def test_over_long_label_truncated_from_the_left():
    name = "a_very_long_filename_that_exceeds_the_limit.png"
    (label,) = _point_labels([Path("dir") / name])
    assert label.startswith("…")
    assert len(label) == _LABEL_MAX
    # the distinguishing tail (extension) is preserved
    assert label.endswith(".png")
