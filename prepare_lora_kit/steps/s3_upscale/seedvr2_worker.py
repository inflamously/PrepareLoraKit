"""Subprocess worker for SeedVR2 batch upscaling."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--response", required=True)
    args = parser.parse_args(argv)

    request_path = Path(args.request)
    response_path = Path(args.response)
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        response = run_request(request)
        response_path.write_text(json.dumps(response, indent=2), encoding="utf-8")
        return 0 if response.get("status") == "ok" else 1
    except BaseException as exc:
        response_path.write_text(
            json.dumps(
                {
                    "status": "error",
                    "error": _format_exception(exc),
                    "processed": [],
                    "failed": {},
                    "warnings": [],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return 1


def run_request(request: dict[str, Any]) -> dict[str, Any]:
    submodule_dir = Path(str(request["submodule_dir"])).expanduser()
    module = _load_seedvr2_module(submodule_dir, bool(request.get("debug", False)))
    _download_models(module, request)

    runner_cache: dict[str, Any] | None = {} if request.get("cache_models", True) else None
    device_list, warnings = _device_list(
        request.get("cuda_device"),
        cache_models=bool(request.get("cache_models", True)),
    )
    residency = _resolve_model_residency(
        request.get("model_residency", "auto"),
        str(request.get("dit_model") or ""),
        device_list[0],
    )

    processed: list[str] = []
    failed: dict[str, str] = {}
    for item in request.get("items", []):
        source = Path(str(item["source"]))
        output = Path(str(item["output"]))
        key = str(item.get("key") or source)
        args = _build_args(request, source, output, residency=residency)
        try:
            frames = module.process_single_file(
                str(source),
                args,
                device_list,
                output_path=str(output),
                format_auto_detected=False,
                runner_cache=runner_cache,
            )
            if frames <= 0:
                raise RuntimeError(f"SeedVR2 produced no output frames for {source.name}")
            if not output.exists():
                raise RuntimeError(f"SeedVR2 did not write expected output: {output}")
            processed.append(key)
        except SystemExit as exc:
            failed[key] = f"SeedVR2 processing exited with code {_format_exit_code(exc)}"
        except BaseException as exc:
            failed[key] = f"SeedVR2 processing failed: {_format_exception(exc)}"

    return {
        "status": "ok",
        "processed": processed,
        "failed": failed,
        "warnings": warnings,
        "model_residency": residency,
    }


def _load_seedvr2_module(submodule_dir: Path, debug_enabled: bool) -> ModuleType:
    cli_path = submodule_dir / "inference_cli.py"
    if not cli_path.exists():
        raise RuntimeError(
            f"SeedVR2 submodule not found at {submodule_dir}; "
            "run `git submodule update --init --recursive third_party/seedvr2`"
        )

    module_name = f"_plk_seedvr2_worker_{abs(hash(str(cli_path.resolve())))}"
    spec = importlib.util.spec_from_file_location(module_name, cli_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import SeedVR2 CLI from {cli_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except SystemExit as exc:
        sys.modules.pop(module_name, None)
        raise RuntimeError(f"SeedVR2 runtime import exited with code {_format_exit_code(exc)}") from exc
    except ModuleNotFoundError as exc:
        sys.modules.pop(module_name, None)
        raise RuntimeError(f"SeedVR2 runtime dependency is missing: {exc.name}") from exc
    except ImportError as exc:
        sys.modules.pop(module_name, None)
        raise RuntimeError(f"SeedVR2 runtime import failed: {exc}") from exc
    except BaseException as exc:
        sys.modules.pop(module_name, None)
        raise RuntimeError(f"SeedVR2 runtime is unavailable: {exc}") from exc

    debug = getattr(module, "debug", None)
    if debug is not None and hasattr(debug, "enabled"):
        debug.enabled = debug_enabled
    return module


def _download_models(module: ModuleType, request: dict[str, Any]) -> None:
    vae_model = getattr(module, "DEFAULT_VAE", "ema_vae_fp16.safetensors")
    try:
        downloaded = module.download_weight(
            dit_model=request.get("dit_model"),
            vae_model=vae_model,
            model_dir=str(request.get("model_dir")),
            debug=getattr(module, "debug", None),
        )
    except SystemExit as exc:
        raise RuntimeError(f"SeedVR2 model download exited with code {_format_exit_code(exc)}") from exc
    except BaseException as exc:
        raise RuntimeError(f"SeedVR2 model download failed: {_format_exception(exc)}") from exc
    if not downloaded:
        raise RuntimeError(
            f"SeedVR2 model download failed for {request.get('dit_model')}; "
            f"check network access and model cache {request.get('model_dir')}"
        )


def _build_args(
    request: dict[str, Any],
    source: Path,
    output: Path,
    *,
    residency: str,
) -> argparse.Namespace:
    cache_models = bool(request.get("cache_models", True))
    cuda_device = request.get("cuda_device")
    devices, _warnings = _device_list(cuda_device, cache_models=cache_models)
    first_device = devices[0]
    if residency == "cpu":
        dit_offload_device = "cpu"
        vae_offload_device = "cpu"
    elif cache_models:
        dit_offload_device = first_device
        vae_offload_device = first_device
    else:
        dit_offload_device = "none"
        vae_offload_device = "none"

    return argparse.Namespace(
        input=str(source),
        output=str(output),
        output_format="png",
        video_backend="opencv",
        use_10bit=False,
        model_dir=str(request.get("model_dir")),
        dit_model=request.get("dit_model"),
        resolution=int(request.get("resolution", 1080)),
        max_resolution=0,
        batch_size=int(request.get("batch_size", 1)),
        uniform_batch_size=False,
        seed=42,
        skip_first_frames=0,
        load_cap=0,
        chunk_size=0,
        prepend_frames=0,
        temporal_overlap=0,
        color_correction="lab",
        input_noise_scale=0.0,
        latent_noise_scale=0.0,
        cuda_device=cuda_device,
        dit_offload_device=dit_offload_device,
        vae_offload_device=vae_offload_device,
        tensor_offload_device="cpu",
        blocks_to_swap=0,
        swap_io_components=False,
        vae_encode_tiled=bool(request.get("vae_tiled", True)),
        vae_encode_tile_size=1024,
        vae_encode_tile_overlap=128,
        vae_decode_tiled=bool(request.get("vae_tiled", True)),
        vae_decode_tile_size=1024,
        vae_decode_tile_overlap=128,
        tile_debug="false",
        attention_mode="sdpa",
        compile_dit=False,
        compile_vae=False,
        compile_backend="inductor",
        compile_mode="default",
        compile_fullgraph=False,
        compile_dynamic=False,
        compile_dynamo_cache_size_limit=64,
        compile_dynamo_recompile_limit=128,
        cache_dit=cache_models,
        cache_vae=cache_models,
        debug=bool(request.get("debug", False)),
    )


def _device_list(cuda_device: object, *, cache_models: bool) -> tuple[list[str], list[str]]:
    if cuda_device:
        devices = [d.strip() for d in str(cuda_device).split(",") if d.strip()]
    else:
        devices = ["0"]
    warnings: list[str] = []
    if cache_models and len(devices) > 1:
        warnings.append(
            "SeedVR2 image batch caching uses a single device; "
            f"using CUDA device {devices[0]} from requested list {','.join(devices)}."
        )
        devices = devices[:1]
    return devices, warnings


def _resolve_model_residency(policy: object, dit_model: str, device_id: str) -> str:
    policy = str(policy or "auto").strip().lower()
    if policy in ("cpu", "gpu"):
        return policy
    if policy != "auto":
        return "cpu"

    try:
        import torch

        if not torch.cuda.is_available():
            return "cpu"
        device_index = int(str(device_id).split(":")[-1])
        total_gb = float(torch.cuda.get_device_properties(device_index).total_memory) / (1024 ** 3)
    except BaseException:
        return "cpu"

    return "gpu" if total_gb >= _minimum_gpu_residency_gb(dit_model) else "cpu"


def _minimum_gpu_residency_gb(dit_model: str) -> float:
    name = dit_model.lower()
    if "7b" in name and "fp16" in name and "fp8" not in name:
        return 40.0
    if "7b" in name:
        return 24.0
    if "fp16" in name and "fp8" not in name:
        return 24.0
    return 16.0


def _format_exit_code(exc: SystemExit) -> str:
    return str(exc.code if exc.code is not None else 0)


def _format_exception(exc: BaseException) -> str:
    message = str(exc).strip()
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__


if __name__ == "__main__":
    raise SystemExit(main())
