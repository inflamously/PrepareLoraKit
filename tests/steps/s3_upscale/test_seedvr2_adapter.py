import json
from pathlib import Path

import pytest
from PIL import Image

from prepare_lora_kit.steps.s3_upscale.seedvr2_catalog import DEFAULT_SEEDVR2_DIT_MODEL
from prepare_lora_kit.steps.s3_upscale.seedvr2_adapter import (
    DEFAULT_SEEDVR2_DIT_MODEL as ADAPTER_DEFAULT_SEEDVR2_DIT_MODEL,
    SeedVR2Unavailable,
    SeedVR2Upscaler,
)
from prepare_lora_kit.steps.s3_upscale.seedvr2_worker import (
    _build_args,
    _resolve_model_residency,
)


def _fake_seedvr2_submodule(path: Path) -> Path:
    path.mkdir()
    (path / "inference_cli.py").write_text(
        """
import json
import os
from pathlib import Path
from PIL import Image

DEFAULT_VAE = "ema_vae_fp16.safetensors"

class Debug:
    def __init__(self):
        self.enabled = False

debug = Debug()

def _log(kind, payload):
    log_path = os.environ.get("PLK_FAKE_SEEDVR2_LOG")
    if not log_path:
        return
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"kind": kind, **payload}) + "\\n")

def download_weight(dit_model, vae_model, model_dir=None, debug=None):
    _log("download", {
        "dit_model": dit_model,
        "vae_model": vae_model,
        "model_dir": model_dir,
        "debug_enabled": getattr(debug, "enabled", None),
    })
    return True

def process_single_file(input_path, args, device_list, output_path=None, format_auto_detected=False, runner_cache=None):
    _log("process", {
        "input_path": input_path,
        "output_path": output_path,
        "format_auto_detected": format_auto_detected,
        "device_list": device_list,
        "runner_cache_id": id(runner_cache) if runner_cache is not None else None,
        "resolution": args.resolution,
        "batch_size": args.batch_size,
        "vae_encode_tiled": args.vae_encode_tiled,
        "vae_decode_tiled": args.vae_decode_tiled,
        "cache_dit": args.cache_dit,
        "cache_vae": args.cache_vae,
        "dit_offload_device": args.dit_offload_device,
        "vae_offload_device": args.vae_offload_device,
    })
    Image.new("RGB", (64, 64), "green").save(output_path)
    return 1
""",
        encoding="utf-8",
    )
    return path


def _read_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_seedvr2_adapter_default_dit_model_comes_from_catalog():
    assert ADAPTER_DEFAULT_SEEDVR2_DIT_MODEL == DEFAULT_SEEDVR2_DIT_MODEL


def test_seedvr2_adapter_batches_outputs_in_one_worker(tmp_path, monkeypatch):
    submodule = _fake_seedvr2_submodule(tmp_path / "seedvr2")
    log_path = tmp_path / "seedvr2_calls.jsonl"
    monkeypatch.setenv("PLK_FAKE_SEEDVR2_LOG", str(log_path))
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first_out = tmp_path / "first_out.png"
    second_out = tmp_path / "second_out.png"
    Image.new("RGB", (32, 24), "red").save(first)
    Image.new("RGB", (32, 24), "blue").save(second)

    upscaler = SeedVR2Upscaler(
        resolution=1024,
        submodule_dir=submodule,
        model_dir=tmp_path / "models",
        dit_model="custom_dit.safetensors",
        cuda_device="1,2",
        batch_size=5,
        vae_tiled=False,
        cache_models=True,
        model_residency="cpu",
        debug=True,
    )

    failures = upscaler.process_many({first: first_out, second: second_out})

    assert failures == {}
    assert first_out.exists()
    assert second_out.exists()
    calls = _read_log(log_path)
    downloads = [call for call in calls if call["kind"] == "download"]
    processes = [call for call in calls if call["kind"] == "process"]
    assert downloads == [
        {
            "kind": "download",
            "dit_model": "custom_dit.safetensors",
            "vae_model": "ema_vae_fp16.safetensors",
            "model_dir": str(tmp_path / "models"),
            "debug_enabled": True,
        }
    ]
    assert len(processes) == 2
    assert [call["input_path"] for call in processes] == [str(first), str(second)]
    assert [call["output_path"] for call in processes] == [str(first_out), str(second_out)]
    assert processes[0]["runner_cache_id"] is not None
    assert processes[0]["runner_cache_id"] == processes[1]["runner_cache_id"]
    assert processes[0]["device_list"] == ["1"]
    assert processes[0]["resolution"] == 1024
    assert processes[0]["batch_size"] == 5
    assert processes[0]["vae_encode_tiled"] is False
    assert processes[0]["vae_decode_tiled"] is False
    assert processes[0]["cache_dit"] is True
    assert processes[0]["cache_vae"] is True
    assert processes[0]["dit_offload_device"] == "cpu"
    assert processes[0]["vae_offload_device"] == "cpu"


def test_seedvr2_adapter_converts_import_system_exit(tmp_path):
    submodule = tmp_path / "seedvr2"
    submodule.mkdir()
    (submodule / "inference_cli.py").write_text("raise SystemExit(7)\n", encoding="utf-8")
    image = tmp_path / "small.png"
    output = tmp_path / "upscaled.png"
    Image.new("RGB", (32, 24), "red").save(image)

    upscaler = SeedVR2Upscaler(resolution=512, submodule_dir=submodule)

    with pytest.raises(SeedVR2Unavailable, match="import exited with code 7"):
        upscaler.process_many({image: output})


def test_seedvr2_adapter_converts_process_system_exit_to_item_failure(tmp_path):
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
        encoding="utf-8",
    )
    image = tmp_path / "small.png"
    output = tmp_path / "upscaled.png"
    Image.new("RGB", (32, 24), "red").save(image)
    upscaler = SeedVR2Upscaler(resolution=512, submodule_dir=submodule)

    failures = upscaler.process_many({image: output})

    assert failures == {str(image): "SeedVR2 processing exited with code 2"}


def test_seedvr2_worker_gpu_residency_uses_inference_device_for_cache():
    args = _build_args(
        {
            "model_dir": "/models",
            "dit_model": DEFAULT_SEEDVR2_DIT_MODEL,
            "resolution": 512,
            "batch_size": 1,
            "vae_tiled": True,
            "cache_models": True,
            "cuda_device": "2",
        },
        Path("in.png"),
        Path("out.png"),
        residency="gpu",
    )

    assert args.dit_offload_device == "2"
    assert args.vae_offload_device == "2"


def test_seedvr2_worker_unknown_residency_falls_back_to_cpu():
    assert _resolve_model_residency("unexpected", DEFAULT_SEEDVR2_DIT_MODEL, "0") == "cpu"
