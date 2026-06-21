from PIL import Image

from prepare_lora_kit.steps.s3_upscale import step as upscale_step


def test_seedvr_without_env_skips_without_lanczos(tmp_path, monkeypatch):
    monkeypatch.delenv("SEEDVR_PATH", raising=False)
    image = tmp_path / "small.png"
    Image.new("RGB", (32, 24), "red").save(image)

    result = upscale_step.run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_model="seedvr",
    )

    assert result["upscaled"] == []
    assert result["skipped"][0]["path"] == str(image)
    assert "SEEDVR_PATH not set" in result["skipped"][0]["reason"]
    with Image.open(image) as img:
        assert img.size == (32, 24)


def test_lanczos_only_runs_when_explicit(tmp_path, monkeypatch):
    monkeypatch.delenv("SEEDVR_PATH", raising=False)
    image = tmp_path / "small.png"
    Image.new("RGB", (32, 24), "red").save(image)

    result = upscale_step.run(
        tmp_path,
        output_dir=tmp_path,
        upscale_target=64,
        upscale_model="lanczos",
        hallucination_ssim_threshold=0.0,
    )

    assert len(result["upscaled"]) == 1
    with Image.open(image) as img:
        assert min(img.size) == 64
