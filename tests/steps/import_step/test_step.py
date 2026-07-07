import json
from pathlib import Path

import pytest
from PIL import Image

from prepare_lora_kit.cancellation import CancelledRun
from prepare_lora_kit.invoke.import_step import invoke_import_step
from prepare_lora_kit.steps.import_step import run
from prepare_lora_kit.steps.import_step.step import get_recursive_mirror_paths
from prepare_lora_kit.pipeline.configs import ImportConfig


def test_import_step_copies_images_and_writes_report(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    report_path = tmp_path / "reports" / "ImportStep_report.json"
    input_dir.mkdir()
    Image.new("RGB", (16, 16), "red").save(input_dir / "first.png")
    Image.new("RGB", (16, 16), "blue").save(input_dir / "second.jpg")
    (input_dir / "notes.txt").write_text("not an image", encoding="utf-8")

    report = run(input_dir, output_dir, report_path=report_path)

    assert sorted(path.name for path in output_dir.iterdir()) == ["first.png", "second.jpg"]
    assert report["count"] == 2
    assert report_path.exists()
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["count"] == 2
    assert len(saved["imported"]) == 2


def test_invoke_import_step_uses_packaged_step_run(tmp_path, monkeypatch):
    from prepare_lora_kit.steps import import_step as import_step_pkg

    captured = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"ok": True}

    working_dir = tmp_path / "working"
    output_dir = tmp_path / "output"
    original_dir = tmp_path / "original"
    working_dir.mkdir()
    original_dir.mkdir()
    (working_dir / "stale.txt").write_text("stale", encoding="utf-8")

    monkeypatch.setattr(import_step_pkg, "run", fake_run)

    result = invoke_import_step(
        working_dir,
        output_dir,
        ImportConfig(),
        original_dir=original_dir,
        enabled_substeps=["import_images"],
    )

    assert result == {"ok": True}
    assert captured["args"] == (original_dir, working_dir)
    assert captured["kwargs"] == {
        "report_path": output_dir / "reports" / "ImportStep_report.json",
        "enabled_substeps": ["import_images"],
        "cancel_check": None,
    }
    assert not (working_dir / "stale.txt").exists()


def test_import_step_preserves_subdir_named_like_input_component(tmp_path):
    fake_image_paths = [tmp_path / "a" / "b" / "img.png", tmp_path / "temp" / "b" / "pytest-58" / "img.png"]

    expected_target_image_paths = [
        Path("a/b/img.png"),
        Path("temp/b/pytest-58/img.png"),
    ]

    for i in range(len(fake_image_paths)):
        result_path = get_recursive_mirror_paths(tmp_path, fake_image_paths[i])
        assert result_path == expected_target_image_paths[i]


@pytest.mark.parametrize(
    "mirror_paths_root, mirror_paths_item, mirror_paths_expected",
    [
        # Image directly at the root -> just the filename, no subpath.
        (Path("/data"), Path("/data/img.png"), Path("img.png")),
        # Plain nested subdirs are mirrored verbatim.
        (Path("/data"), Path("/data/a/b/img.png"), Path("a/b/img.png")),
        # A subfolder whose name matches a *component* of the root (the original
        # membership-filter bug): the inner "data" must survive.
        (Path("/srv/data"), Path("/srv/data/data/img.png"), Path("data/img.png")),
        # The full root string recurs deeper in the path (the str.replace
        # replace-all edge): only the prefix is stripped, the inner copy stays.
        (Path("/data"), Path("/data/sub/data/img.png"), Path("sub/data/img.png")),
        # Repeated component names at multiple depths are all preserved.
        (Path("/a"), Path("/a/a/a/img.png"), Path("a/a/img.png")),
        # Root with several components, deep nesting after it.
        (Path("/home/user/photos"), Path("/home/user/photos/2024/trip/x.jpg"),
         Path("2024/trip/x.jpg")),
    ],
)
def test_get_recursive_mirror_paths_strips_only_the_prefix(mirror_paths_root, mirror_paths_item, mirror_paths_expected):
    assert get_recursive_mirror_paths(mirror_paths_root, mirror_paths_item) == mirror_paths_expected


def test_get_recursive_mirror_paths_rejects_path_outside_root(tmp_path):
    """relative_to raises if the item isn't under root — an invariant os.walk
    guarantees, so a violation should fail loud rather than silently mangle."""
    with pytest.raises(ValueError):
        get_recursive_mirror_paths(tmp_path / "input", tmp_path / "elsewhere" / "img.png")


def test_import_step_removes_partial_output_when_cancelled(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    Image.new("RGB", (16, 16), "red").save(input_dir / "first.png")
    Image.new("RGB", (16, 16), "blue").save(input_dir / "second.jpg")
    checks = 0

    def cancel_after_first_copy():
        nonlocal checks
        checks += 1
        if checks >= 3:
            raise CancelledRun("Run cancelled")

    with pytest.raises(CancelledRun):
        run(input_dir, output_dir, cancel_check=cancel_after_first_copy)

    assert not output_dir.exists()
