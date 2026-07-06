from pathlib import Path

import pytest
from PIL import Image

from prepare_lora_kit.cancellation import CancelledRun
from prepare_lora_kit.steps.upscale import step as upscale_step


def _image(path: Path, size: tuple[int, int], color: str = "red") -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def _write_upscaled(size: tuple[int, int] = (72, 64)):
    def upscaler(_path: Path, output_path: Path) -> Path:
        Image.new("RGB", size, "blue").save(output_path)
        return output_path

    return upscaler


def test_seedvr2_missing_submodule_skips_without_lanczos(tmp_path):
    image = _image(tmp_path / "small.png", (32, 24))

    result = upscale_step.run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_model="seedvr2",
        seedvr2_submodule_dir=str(tmp_path / "missing_seedvr2"),
    )

    assert result["upscaled"] == []
    assert result["skipped"][0]["path"] == str(image)
    assert "SeedVR2 submodule not found" in result["skipped"][0]["reason"]
    with Image.open(image) as img:
        assert img.size == (32, 24)


def test_seedvr2_step_batches_candidates_once(tmp_path, monkeypatch):
    first = _image(tmp_path / "first.png", (32, 24), "red")
    second = _image(tmp_path / "second.png", (40, 30), "blue")
    calls = []

    class FakeSeedVR2Upscaler:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def prepare(self):
            pass

        def process_many(self, outputs_by_source, *, sources_by_path=None, cancel_check=None):
            calls.append((self.kwargs, dict(outputs_by_source)))
            for output_path in outputs_by_source.values():
                Image.new("RGB", (72, 64), "green").save(output_path)
            return {}

    monkeypatch.setattr(upscale_step, "SeedVR2Upscaler", FakeSeedVR2Upscaler)
    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 1.0)

    result = upscale_step.run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_model="seedvr2",
        seedvr2_model_residency="cpu",
    )

    assert len(calls) == 1
    kwargs, outputs_by_source = calls[0]
    assert kwargs["model_residency"] == "cpu"
    assert set(outputs_by_source) == {first, second}
    assert len(result["upscaled"]) == 2
    with Image.open(first) as img:
        assert img.size == (72, 64)
    with Image.open(second) as img:
        assert img.size == (72, 64)


def test_seedvr2_step_cancellation_removes_all_temp_files(tmp_path, monkeypatch):
    first = _image(tmp_path / "first.png", (32, 24), "red")
    second = _image(tmp_path / "second.png", (40, 30), "blue")

    class FakeSeedVR2Upscaler:
        def __init__(self, **_kwargs):
            pass

        def prepare(self):
            pass

        def process_many(self, outputs_by_source, *, sources_by_path=None, cancel_check=None):
            for output_path in outputs_by_source.values():
                Image.new("RGB", (72, 64), "green").save(output_path)
            raise CancelledRun("Run cancelled")

    monkeypatch.setattr(upscale_step, "SeedVR2Upscaler", FakeSeedVR2Upscaler)

    with pytest.raises(CancelledRun):
        upscale_step.run(
            tmp_path,
            output_dir=tmp_path,
            upscale_target=64,
            upscale_model="seedvr2",
        )

    assert not (tmp_path / "first.upscaling.tmp.png").exists()
    assert not (tmp_path / "second.upscaling.tmp.png").exists()
    with Image.open(first) as img:
        assert img.size == (32, 24)
    with Image.open(second) as img:
        assert img.size == (40, 30)


def test_seedvr_alias_warns_and_uses_injected_upscaler(tmp_path, monkeypatch):
    image = _image(tmp_path / "small.png", (32, 24))
    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 1.0)

    with pytest.warns(DeprecationWarning, match="upscale_model=seedvr"):
        result = upscale_step.run(
            tmp_path,
            output_dir=tmp_path,
            upscale_target=64,
            upscale_model="seedvr",
            upscaler=_write_upscaled(),
        )

    assert len(result["upscaled"]) == 1
    with Image.open(image) as img:
        assert img.size == (72, 64)


def test_pass_through_copies_large_images_to_separate_output(tmp_path):
    image = _image(tmp_path / "large.png", (80, 96))
    output_dir = tmp_path / "out"

    result = upscale_step.run(
        tmp_path,
        output_dir=output_dir,
        upscale_target=64,
        upscale_model="lanczos",
    )

    copied = output_dir / image.name
    assert result["skipped"] == [str(image)]
    assert copied.exists()
    with Image.open(copied) as img:
        assert img.size == (80, 96)


def test_in_place_upscale_uses_temp_file_before_accepting(tmp_path, monkeypatch):
    image = _image(tmp_path / "small.png", (32, 24))
    seen_original_sizes = []

    def upscaler(path: Path, output_path: Path) -> Path:
        assert output_path != path
        assert ".upscaling.tmp" in output_path.name
        with Image.open(path) as img:
            seen_original_sizes.append(img.size)
        Image.new("RGB", (72, 64), "blue").save(output_path)
        return output_path

    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 1.0)

    result = upscale_step.run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_model="custom",
        upscaler=upscaler,
    )

    assert seen_original_sizes == [(32, 24)]
    assert len(result["upscaled"]) == 1
    assert not (tmp_path / "small.upscaling.tmp.png").exists()
    with Image.open(image) as img:
        assert img.size == (72, 64)


def test_cancelled_upscale_removes_temp_file(tmp_path):
    image = _image(tmp_path / "small.png", (32, 24))
    checks = 0

    def upscaler(_path: Path, output_path: Path) -> Path:
        Image.new("RGB", (72, 64), "blue").save(output_path)
        return output_path

    def cancel_after_upscaler():
        nonlocal checks
        checks += 1
        if checks >= 5:
            raise CancelledRun("Run cancelled")

    with pytest.raises(CancelledRun):
        upscale_step.run(
            tmp_path,
            output_dir=tmp_path,
            upscale_target=64,
            upscale_model="custom",
            upscaler=upscaler,
            cancel_check=cancel_after_upscaler,
        )

    assert not (tmp_path / "small.upscaling.tmp.png").exists()
    with Image.open(image) as img:
        assert img.size == (32, 24)


def test_rejected_upscale_keeps_original_and_removes_temp(tmp_path, monkeypatch):
    image = _image(tmp_path / "small.png", (32, 24))
    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 0.1)

    result = upscale_step.run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_model="custom",
        upscaler=_write_upscaled(),
        hallucination_ssim_threshold=0.6,
    )

    assert result["upscaled"] == []
    assert result["rejected_post"][0]["path"] == str(image)
    assert not (tmp_path / "small.upscaling.tmp.png").exists()
    with Image.open(image) as img:
        assert img.size == (32, 24)


def test_custom_upscaler_runs_when_injected(tmp_path, monkeypatch):
    image = _image(tmp_path / "small.png", (32, 24))
    output_dir = tmp_path / "out"
    calls = []

    def upscaler(path: Path, output_path: Path) -> Path:
        calls.append((path, output_path))
        Image.new("RGB", (72, 64), "blue").save(output_path)
        return output_path

    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 1.0)

    result = upscale_step.run(
        tmp_path,
        output_dir=output_dir,
        upscale_target=64,
        upscale_model="custom",
        upscaler=upscaler,
    )

    assert calls and calls[0][0] == image
    assert result["upscaled"][0]["upscaled"] == str(output_dir / image.name)
    with Image.open(output_dir / image.name) as img:
        assert img.size == (72, 64)


def test_blank_upscaler_exception_records_non_empty_skip_reason(tmp_path):
    image = _image(tmp_path / "small.png", (32, 24))

    def upscaler(_path: Path, _output_path: Path) -> Path:
        raise RuntimeError()

    result = upscale_step.run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_model="custom",
        upscaler=upscaler,
    )

    assert result["upscaled"] == []
    assert result["skipped"][0]["path"] == str(image)
    assert result["skipped"][0]["reason"] == "RuntimeError"
    with Image.open(image) as img:
        assert img.size == (32, 24)


def test_lanczos_only_runs_when_explicit(tmp_path, monkeypatch):
    _image(tmp_path / "small.png", (32, 24))
    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 1.0)

    result = upscale_step.run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_model="lanczos",
        hallucination_ssim_threshold=0.0,
    )

    assert len(result["upscaled"]) == 1
    with Image.open(tmp_path / "small.png") as img:
        assert min(img.size) == 64


def test_partition_flags_resolution_and_jpeg_boundaries_with_seedvr2(tmp_path):
    critical = _image(tmp_path / "critical.png", (1000, 1000))
    mid_png = _image(tmp_path / "mid.png", (2000, 2000))
    mid_jpg = _image(tmp_path / "mid.jpg", (2000, 2000))
    large_png = _image(tmp_path / "large.png", (4000, 4000))
    large_jpg = _image(tmp_path / "large.jpg", (4000, 4000))

    partitions = upscale_step._partition_images(
        tmp_path, upscale_target=3072, upscale_highlight_threshold=1536,
        enable_seedvr2_cleanup=True,
    )
    by_name = {info.path.name: info for info in partitions.images}

    assert by_name[critical.name].planned_action == "upscale"
    assert by_name[critical.name].flagged is True
    assert by_name[critical.name].needs_pre_downscale is False

    assert by_name[mid_png.name].planned_action == "upscale"
    assert by_name[mid_png.name].flagged is False
    assert by_name[mid_png.name].needs_pre_downscale is False

    assert by_name[mid_jpg.name].planned_action == "upscale"
    assert by_name[mid_jpg.name].flagged is True
    assert by_name[mid_jpg.name].needs_pre_downscale is True

    assert by_name[large_png.name].planned_action == "pass_through"
    assert by_name[large_png.name].flagged is False

    assert by_name[large_jpg.name].planned_action == "jpeg_cleanup"
    assert by_name[large_jpg.name].flagged is True
    assert by_name[large_jpg.name].needs_pre_downscale is True


def test_partition_disables_cleanup_tricks_without_seedvr2(tmp_path):
    mid_jpg = _image(tmp_path / "mid.jpg", (2000, 2000))
    large_jpg = _image(tmp_path / "large.jpg", (4000, 4000))

    partitions = upscale_step._partition_images(
        tmp_path, upscale_target=3072, upscale_highlight_threshold=1536,
        enable_seedvr2_cleanup=False,
    )
    by_name = {info.path.name: info for info in partitions.images}

    # No shrink-then-regrow trick under a non-generative model: the mid JPEG is a
    # plain upscale (no pre-downscale) and the large JPEG is left untouched.
    assert by_name[mid_jpg.name].planned_action == "upscale"
    assert by_name[mid_jpg.name].needs_pre_downscale is False
    assert by_name[mid_jpg.name].flagged is False

    assert by_name[large_jpg.name].planned_action == "pass_through"
    assert by_name[large_jpg.name].needs_pre_downscale is False
    assert by_name[large_jpg.name].flagged is False


def test_lanczos_jpeg_source_converts_to_png_and_removes_original(tmp_path, monkeypatch):
    image_path = _image(tmp_path / "small.jpg", (32, 24))
    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 1.0)

    result = upscale_step.run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_model="lanczos",
    )

    png_path = tmp_path / "small.png"
    assert len(result["upscaled"]) == 1
    assert result["upscaled"][0]["upscaled"] == str(png_path)
    assert png_path.exists()
    assert not image_path.exists()
    with Image.open(png_path) as img:
        assert min(img.size) == 64


def test_pre_downscale_wrapper_used_for_jpeg_candidates_under_seedvr2(tmp_path, monkeypatch):
    # An injected upscaler with upscale_model="seedvr2" exercises the generative
    # pre-downscale path (the only path that shrinks before upscaling).
    image_path = _image(tmp_path / "mid.jpg", (100, 100))
    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 1.0)

    calls = []
    real_write = upscale_step._write_downscaled_copy

    def spy(path, scratch_dir):
        calls.append(path)
        return real_write(path, scratch_dir)

    monkeypatch.setattr(upscale_step, "_write_downscaled_copy", spy)

    def upscaler(path: Path, output_path: Path) -> Path:
        Image.new("RGB", (200, 200), "blue").save(output_path)
        return output_path

    result = upscale_step.run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=200,
        upscale_highlight_threshold=50,
        upscale_model="seedvr2",
        upscaler=upscaler,
    )

    assert calls == [image_path]
    png_path = tmp_path / "mid.png"
    assert len(result["upscaled"]) == 1
    assert png_path.exists()


def test_lanczos_does_not_pre_downscale_jpeg_candidates(tmp_path, monkeypatch):
    # Under Lanczos the shrink-then-regrow trick is off (it would blur), so the
    # JPEG is upscaled directly without any pre-downscale.
    _image(tmp_path / "mid.jpg", (100, 100))
    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 1.0)

    def boom(*_args, **_kwargs):
        raise AssertionError("pre-downscale must not run under Lanczos")

    monkeypatch.setattr(upscale_step, "_write_downscaled_copy", boom)

    result = upscale_step.run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=200,
        upscale_highlight_threshold=50,
        upscale_model="lanczos",
    )

    assert len(result["upscaled"]) == 1
    assert (tmp_path / "mid.png").exists()


def test_lanczos_leaves_large_jpeg_untouched(tmp_path):
    image_path = _image(tmp_path / "large.jpg", (200, 200))

    result = upscale_step.run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_highlight_threshold=64,
        upscale_model="lanczos",
    )

    # Large JPEG, but Lanczos can't clean it, so it passes through unchanged.
    assert result["upscaled"] == []
    assert image_path.exists()
    assert not (tmp_path / "large.png").exists()


def test_jpeg_cleanup_runs_under_seedvr2(tmp_path, monkeypatch):
    image_path = _image(tmp_path / "large.jpg", (200, 200))
    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 1.0)

    class FakeSeedVR2Upscaler:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def prepare(self):
            pass

        def process_many(self, outputs_by_source, *, sources_by_path=None, cancel_check=None):
            # Cleanup must feed the model a pre-downscaled copy, not the raw JPEG.
            assert sources_by_path and set(sources_by_path) == set(outputs_by_source)
            for output_path in outputs_by_source.values():
                Image.new("RGB", (300, 300), "green").save(output_path)
            return {}

    monkeypatch.setattr(upscale_step, "SeedVR2Upscaler", FakeSeedVR2Upscaler)

    result = upscale_step.run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_highlight_threshold=64,
        upscale_model="seedvr2",
    )

    png_path = tmp_path / "large.png"
    assert len(result["upscaled"]) == 1
    assert result["upscaled"][0]["original"] == str(image_path)
    assert png_path.exists()
    assert not image_path.exists()


def test_jpeg_cleanup_leaves_original_untouched_when_seedvr2_unavailable(tmp_path):
    image_path = _image(tmp_path / "large.jpg", (200, 200))

    result = upscale_step.run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_highlight_threshold=64,
        upscale_model="seedvr2",
        seedvr2_submodule_dir=str(tmp_path / "missing_seedvr2"),
    )

    assert image_path.exists()
    assert not (tmp_path / "large.png").exists()
    assert result["skipped"][0]["path"] == str(image_path)
    assert "jpeg_cleanup unavailable" in result["skipped"][0]["reason"]


def test_dest_collision_keeps_jpeg_untouched(tmp_path, monkeypatch):
    # foo.jpg would convert to foo.png and clobber the existing foo.png.
    jpg = _image(tmp_path / "foo.jpg", (40, 40))
    png = _image(tmp_path / "foo.png", (40, 40))
    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 1.0)

    result = upscale_step.run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_model="lanczos",
    )

    # The JPEG is left as-is; the PNG is free to upscale to its own path.
    assert jpg.exists()
    with Image.open(jpg) as img:
        assert img.size == (40, 40)
    assert {entry["original"] for entry in result["upscaled"]} == {str(png)}


def test_upscale_review_called_only_when_flagged_and_skip_forces_pass_through(tmp_path, monkeypatch):
    flagged_image = _image(tmp_path / "flagged.png", (40, 40))
    _image(tmp_path / "ok.png", (4000, 4000))
    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 1.0)

    calls = []

    class FakeInteraction:
        def upscale_review(self, items):
            calls.append(items)
            return {str(flagged_image): "skip"}

    result = upscale_step.run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_model="lanczos",
        interaction=FakeInteraction(),
    )

    assert len(calls) == 1
    assert [item["path"] for item in calls[0]] == [str(flagged_image)]
    assert result["upscaled"] == []
    assert flagged_image.exists()
    with Image.open(flagged_image) as img:
        assert img.size == (40, 40)


def test_upscale_review_not_called_when_nothing_flagged(tmp_path):
    image_path = _image(tmp_path / "ok.png", (4000, 4000))

    class FailingInteraction:
        def upscale_review(self, items):
            raise AssertionError("upscale_review should not be called when nothing is flagged")

    result = upscale_step.run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_model="lanczos",
        interaction=FailingInteraction(),
    )

    assert result["skipped"] == [str(image_path)]
