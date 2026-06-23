from pathlib import Path

import pytest
from PIL import Image

from prepare_lora_kit.cancellation import CancelledRun
from prepare_lora_kit.steps.s3_upscale import step as upscale_step


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
