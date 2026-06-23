from pathlib import Path

import pytest
from PIL import Image

from prepare_lora_kit.steps.s3_upscale.seedvr2_catalog import DEFAULT_SEEDVR2_DIT_MODEL
from prepare_lora_kit.steps.s3_upscale.seedvr2_adapter import (
    DEFAULT_SEEDVR2_DIT_MODEL as ADAPTER_DEFAULT_SEEDVR2_DIT_MODEL,
    SeedVR2Unavailable,
    SeedVR2Upscaler,
)


def _fake_seedvr2_submodule(path: Path) -> Path:
    path.mkdir()
    (path / "inference_cli.py").write_text(
        """
from pathlib import Path
from PIL import Image

DEFAULT_VAE = "ema_vae_fp16.safetensors"

class Debug:
    def __init__(self):
        self.enabled = False

debug = Debug()
download_calls = []
process_calls = []

def download_weight(dit_model, vae_model, model_dir=None, debug=None):
    download_calls.append({
        "dit_model": dit_model,
        "vae_model": vae_model,
        "model_dir": model_dir,
        "debug_enabled": getattr(debug, "enabled", None),
    })
    return True

def process_single_file(input_path, args, device_list, output_path=None, format_auto_detected=False, runner_cache=None):
    process_calls.append({
        "input_path": input_path,
        "output_path": output_path,
        "format_auto_detected": format_auto_detected,
        "device_list": device_list,
        "runner_cache_id": id(runner_cache) if runner_cache is not None else None,
        "args": args,
    })
    Image.new("RGB", (64, 64), "green").save(output_path)
    return 1
""",
    )
    return path


def test_seedvr2_adapter_imports_downloads_and_processes_output(tmp_path):
    submodule = _fake_seedvr2_submodule(tmp_path / "seedvr2")
    image = tmp_path / "small.png"
    output = tmp_path / "upscaled.png"
    Image.new("RGB", (32, 24), "red").save(image)

    upscaler = SeedVR2Upscaler(
        resolution=1024,
        submodule_dir=submodule,
        model_dir=tmp_path / "models",
        dit_model="custom_dit.safetensors",
        cuda_device="1,2",
        batch_size=5,
        vae_tiled=False,
        cache_models=True,
        debug=True,
    )

    assert upscaler(image, output) == output

    module = upscaler._load_module()
    assert len(module.download_calls) == 1
    assert module.download_calls[0] == {
        "dit_model": "custom_dit.safetensors",
        "vae_model": "ema_vae_fp16.safetensors",
        "model_dir": str(tmp_path / "models"),
        "debug_enabled": True,
    }
    assert len(module.process_calls) == 1
    call = module.process_calls[0]
    assert call["input_path"] == str(image)
    assert call["output_path"] == str(output)
    assert call["format_auto_detected"] is False
    assert call["device_list"] == ["1", "2"]
    assert call["args"].resolution == 1024
    assert call["args"].batch_size == 5
    assert call["args"].vae_encode_tiled is False
    assert call["args"].vae_decode_tiled is False
    assert call["args"].cache_dit is True
    assert call["args"].cache_vae is True
    assert output.exists()


def test_seedvr2_adapter_default_dit_model_comes_from_catalog():
    assert ADAPTER_DEFAULT_SEEDVR2_DIT_MODEL == DEFAULT_SEEDVR2_DIT_MODEL


def test_seedvr2_adapter_reuses_download_and_runner_cache(tmp_path):
    submodule = _fake_seedvr2_submodule(tmp_path / "seedvr2")
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    Image.new("RGB", (32, 24), "red").save(first)
    Image.new("RGB", (32, 24), "blue").save(second)

    upscaler = SeedVR2Upscaler(
        resolution=512,
        submodule_dir=submodule,
        model_dir=tmp_path / "models",
        cache_models=True,
    )

    upscaler(first, tmp_path / "first_out.png")
    upscaler(second, tmp_path / "second_out.png")

    module = upscaler._load_module()
    assert len(module.download_calls) == 1
    assert module.download_calls[0]["dit_model"] == DEFAULT_SEEDVR2_DIT_MODEL
    cache_ids = [call["runner_cache_id"] for call in module.process_calls]
    assert len(cache_ids) == 2
    assert cache_ids[0] is not None
    assert cache_ids[0] == cache_ids[1]


def test_seedvr2_adapter_converts_import_system_exit(tmp_path):
    submodule = tmp_path / "seedvr2"
    submodule.mkdir()
    (submodule / "inference_cli.py").write_text("raise SystemExit(7)\n")

    upscaler = SeedVR2Upscaler(resolution=512, submodule_dir=submodule)

    with pytest.raises(SeedVR2Unavailable, match="import exited with code 7"):
        upscaler.prepare()


def test_seedvr2_adapter_converts_process_system_exit(tmp_path):
    submodule = tmp_path / "seedvr2"
    submodule.mkdir()
    (submodule / "inference_cli.py").write_text(
        """
DEFAULT_VAE = "ema_vae_fp16.safetensors"
debug = None

def download_weight(dit_model, vae_model, model_dir=None, debug=None):
    return True

def process_single_file(input_path, args, device_list, output_path=None, format_auto_detected=False, runner_cache=None):
    raise SystemExit(2)
""",
    )
    image = tmp_path / "small.png"
    output = tmp_path / "upscaled.png"
    Image.new("RGB", (32, 24), "red").save(image)
    upscaler = SeedVR2Upscaler(resolution=512, submodule_dir=submodule)

    with pytest.raises(RuntimeError, match="processing exited with code 2"):
        upscaler(image, output)
