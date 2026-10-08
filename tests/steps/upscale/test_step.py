from pathlib import Path

import pytest
from PIL import Image

from prepare_lora_kit.cancellation import CancelledRun, noop_cancel_check
from prepare_lora_kit.pipeline.configs import UpscaleConfig
from prepare_lora_kit.steps.context import StepRunContext
from prepare_lora_kit.steps.upscale import step as upscale_step


def _image(path: Path, size: tuple[int, int], color: str = "red") -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def _write_upscaled(size: tuple[int, int] = (72, 64)):
    def upscaler(_path: Path, output_path: Path) -> Path:
        Image.new("RGB", size, "blue").save(output_path)
        return output_path

    return upscaler


def _run(
    dataset_dir: Path,
    *,
    output_dir: Path | None = None,
    report_path: Path | None = None,
    interaction=None,
    enabled_substeps=None,
    cancel_check=noop_cancel_check,
    upscaler=None,
    **config_kwargs,
):
    return upscale_step.run(
        dataset_dir,
        UpscaleConfig(**config_kwargs),
        context=StepRunContext(
            output_dir=output_dir,
            report_path=report_path,
            interaction=interaction,
            enabled_substeps=enabled_substeps,
            cancel_check=cancel_check,
        ),
        upscaler=upscaler,
    )


def test_seedvr2_missing_submodule_skips_without_lanczos(tmp_path):
    image = _image(tmp_path / "small.png", (32, 24))

    result = _run(
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

    result = _run(
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
        _run(
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
        result = _run(
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

    result = _run(
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

    result = _run(
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
        _run(
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

    result = _run(
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

    result = _run(
        tmp_path,
        output_dir=output_dir,
        upscale_target=64,
        upscale_model="custom",
        upscaler=upscaler,
    )

    assert calls
    assert calls[0][0] == image
    assert result["upscaled"][0]["upscaled"] == str(output_dir / image.name)
    with Image.open(output_dir / image.name) as img:
        assert img.size == (72, 64)


def test_blank_upscaler_exception_records_non_empty_skip_reason(tmp_path):
    image = _image(tmp_path / "small.png", (32, 24))

    def upscaler(_path: Path, _output_path: Path) -> Path:
        raise RuntimeError()

    result = _run(
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

    result = _run(
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
    # plain upscale (no pre-downscale). The large JPEG is still cleaned up to a
    # same-size PNG (by denoise), just never pre-downscaled.
    assert by_name[mid_jpg.name].planned_action == "upscale"
    assert by_name[mid_jpg.name].needs_pre_downscale is False
    assert by_name[mid_jpg.name].flagged is False

    assert by_name[large_jpg.name].planned_action == "jpeg_cleanup"
    assert by_name[large_jpg.name].needs_pre_downscale is False
    assert by_name[large_jpg.name].flagged is True


def test_lanczos_jpeg_source_converts_to_png_and_removes_original(tmp_path, monkeypatch):
    image_path = _image(tmp_path / "small.jpg", (32, 24))
    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 1.0)

    result = _run(
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

    result = _run(
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

    result = _run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=200,
        upscale_highlight_threshold=50,
        upscale_model="lanczos",
    )

    assert len(result["upscaled"]) == 1
    assert (tmp_path / "mid.png").exists()


def test_lanczos_denoises_large_jpeg_to_same_size_png(tmp_path):
    image_path = _image(tmp_path / "large.jpg", (200, 150))

    result = _run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_highlight_threshold=64,
        upscale_model="lanczos",
    )

    # Lanczos can't restore it, but the JPEG still lands as a denoised PNG.
    png_path = tmp_path / "large.png"
    assert result["upscaled"] == [
        {"original": str(image_path), "upscaled": str(png_path), "method": "denoise"},
    ]
    assert not image_path.exists()
    with Image.open(png_path) as img:
        assert img.size == (200, 150)


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
            assert sources_by_path
            assert set(sources_by_path) == set(outputs_by_source)
            for output_path in outputs_by_source.values():
                Image.new("RGB", (300, 300), "green").save(output_path)
            return {}

    monkeypatch.setattr(upscale_step, "SeedVR2Upscaler", FakeSeedVR2Upscaler)

    result = _run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_highlight_threshold=64,
        upscale_model="seedvr2",
    )

    png_path = tmp_path / "large.png"
    assert len(result["upscaled"]) == 1
    assert result["upscaled"][0]["original"] == str(image_path)
    assert not image_path.exists()
    # The model wrote 300x300; cleanup keeps the source resolution exactly.
    with Image.open(png_path) as img:
        assert img.size == (200, 200)


def test_jpeg_cleanup_falls_back_to_denoise_when_seedvr2_unavailable(tmp_path):
    image_path = _image(tmp_path / "large.jpg", (200, 200))

    result = _run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_highlight_threshold=64,
        upscale_model="seedvr2",
        seedvr2_submodule_dir=str(tmp_path / "missing_seedvr2"),
    )

    assert not image_path.exists()
    assert result["skipped"] == []
    assert result["upscaled"][0]["method"] == "denoise"
    with Image.open(tmp_path / "large.png") as img:
        assert img.size == (200, 200)


def test_dest_collision_keeps_jpeg_untouched(tmp_path, monkeypatch):
    # foo.jpg would convert to foo.png and clobber the existing foo.png.
    jpg = _image(tmp_path / "foo.jpg", (40, 40))
    png = _image(tmp_path / "foo.png", (40, 40))
    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 1.0)

    result = _run(
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


def test_upscale_review_skip_forces_pass_through(tmp_path, monkeypatch):
    flagged_image = _image(tmp_path / "flagged.png", (40, 40))
    _image(tmp_path / "ok.png", (4000, 4000))
    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 1.0)

    calls = []

    class FakeInteraction:
        def upscale_review(self, items):
            calls.append(items)
            return {str(flagged_image): "skip"}

    result = _run(
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


def test_upscale_review_not_called_without_candidates(tmp_path):
    image_path = _image(tmp_path / "ok.png", (4000, 4000))

    class FailingInteraction:
        def upscale_review(self, items):
            raise AssertionError("upscale_review should not be called without candidates")

    result = _run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_model="lanczos",
        interaction=FailingInteraction(),
    )

    assert result["skipped"] == [str(image_path)]


class _RecordingInteraction:
    def __init__(self, decide=None):
        self.items = None
        self._decide = decide or (lambda _item: None)

    def upscale_review(self, items):
        self.items = items
        return {
            item["path"]: decision
            for item in items
            if (decision := self._decide(item)) is not None
        }


def _fake_seedvr2(output_size: tuple[int, int]):
    class FakeSeedVR2Upscaler:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def prepare(self):
            pass

        def process_many(self, outputs_by_source, *, sources_by_path=None, cancel_check=None):
            for output_path in outputs_by_source.values():
                Image.new("RGB", output_size, "green").save(output_path)
            return {}

    return FakeSeedVR2Upscaler


def test_upscale_review_lists_unflagged_candidates_with_tiers(tmp_path, monkeypatch):
    _image(tmp_path / "low.png", (300, 400))
    _image(tmp_path / "mid.png", (2000, 2100))
    _image(tmp_path / "big.jpg", (3100, 3200))
    _image(tmp_path / "done.png", (4000, 4000))
    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 1.0)
    interaction = _RecordingInteraction(lambda _item: "skip")

    _run(
        tmp_path,
        output_dir=tmp_path / "out",
        upscale_target=3072,
        upscale_highlight_threshold=1536,
        upscale_model="lanczos",
        interaction=interaction,
    )

    by_name = {item["name"]: item for item in interaction.items}
    # mid.png is not flagged (above the highlight threshold) but is still reviewable.
    assert set(by_name) == {"low.png", "mid.png", "big.jpg"}
    assert by_name["mid.png"]["flagged"] is False
    assert (by_name["low.png"]["tier_lo"], by_name["low.png"]["tier_hi"]) == (256, 511)
    assert (by_name["mid.png"]["tier_lo"], by_name["mid.png"]["tier_hi"]) == (1792, 2047)
    assert by_name["big.jpg"]["tier_lo"] == 3072
    assert by_name["big.jpg"]["target"] == 3072
    assert by_name["big.jpg"]["initial_decision"] == "cleanup"
    assert by_name["low.png"]["initial_decision"] == "upscale"


def test_review_cleanup_converts_jpeg_to_same_size_png(tmp_path):
    jpg = _image(tmp_path / "photo.jpg", (120, 90))

    result = _run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=256,
        upscale_model="lanczos",
        interaction=_RecordingInteraction(lambda _item: "cleanup"),
    )

    assert not jpg.exists()
    with Image.open(tmp_path / "photo.png") as img:
        assert img.size == (120, 90)
    assert result["upscaled"][0]["method"] == "denoise"


def test_review_cleanup_on_non_jpeg_keeps_planned_action(tmp_path, monkeypatch):
    png = _image(tmp_path / "small.png", (32, 24))
    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 1.0)

    result = _run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_model="lanczos",
        interaction=_RecordingInteraction(lambda _item: "cleanup"),
    )

    assert [entry["original"] for entry in result["upscaled"]] == [str(png)]
    with Image.open(png) as img:
        assert min(img.size) == 64


def test_review_upscale_above_target_keeps_cleanup(tmp_path):
    jpg = _image(tmp_path / "big.jpg", (200, 200))

    _run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_model="lanczos",
        interaction=_RecordingInteraction(lambda _item: "upscale"),
    )

    # "upscale" doesn't apply above the target, so the planned cleanup runs.
    assert not jpg.exists()
    with Image.open(tmp_path / "big.png") as img:
        assert img.size == (200, 200)


def test_review_skip_keeps_large_jpeg_as_is(tmp_path):
    jpg = _image(tmp_path / "big.jpg", (200, 200))

    _run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_model="lanczos",
        interaction=_RecordingInteraction(lambda _item: "skip"),
    )

    assert jpg.exists()
    assert not (tmp_path / "big.png").exists()


def test_review_cleanup_collision_keeps_jpeg(tmp_path):
    # big.jpg would become big.png and clobber the existing (also reviewed) PNG.
    jpg = _image(tmp_path / "big.jpg", (200, 200))
    png = _image(tmp_path / "big.png", (40, 40))
    decisions = {str(jpg): "cleanup", str(png): "skip"}

    _run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_model="lanczos",
        interaction=_RecordingInteraction(lambda item: decisions.get(item["path"])),
    )

    assert jpg.exists()
    with Image.open(png) as img:
        assert img.size == (40, 40)


def test_rejected_seedvr2_cleanup_falls_back_to_denoised_png(tmp_path, monkeypatch):
    jpg = _image(tmp_path / "large.jpg", (200, 200))
    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 0.0)
    monkeypatch.setattr(upscale_step, "SeedVR2Upscaler", _fake_seedvr2((200, 200)))

    result = _run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_highlight_threshold=64,
        upscale_model="seedvr2",
    )

    assert [entry["path"] for entry in result["rejected_post"]] == [str(jpg)]
    assert result["upscaled"][0]["method"] == "denoise"
    assert not jpg.exists()
    with Image.open(tmp_path / "large.png") as img:
        assert img.size == (200, 200)


def test_seedvr2_cleanup_targets_own_min_side(tmp_path, monkeypatch):
    _image(tmp_path / "wide.jpg", (300, 200))
    monkeypatch.setattr(upscale_step, "_hallucination_check", lambda *_args: 1.0)
    built = []
    fake = _fake_seedvr2((304, 208))

    class Recording(fake):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            built.append(kwargs["resolution"])

    monkeypatch.setattr(upscale_step, "SeedVR2Upscaler", Recording)

    _run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_highlight_threshold=64,
        upscale_model="seedvr2",
    )

    # Probe at the target, then the real worker at the image's own min-side.
    assert built[-1] == 200
    with Image.open(tmp_path / "wide.png") as img:
        assert img.size == (300, 200)
