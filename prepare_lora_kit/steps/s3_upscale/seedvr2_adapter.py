"""Direct-import adapter for the optional SeedVR2 submodule."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from .seedvr2_catalog import DEFAULT_SEEDVR2_DIT_MODEL

DEFAULT_SEEDVR2_MODEL_DIR = "~/.cache/prepare_lora_kit/seedvr2"


class SeedVR2Unavailable(RuntimeError):
    """Raised when the optional SeedVR2 runtime cannot be used."""


def default_seedvr2_submodule_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "third_party" / "seedvr2"


class SeedVR2Upscaler:
    """Lazily import SeedVR2's standalone CLI and process one image at a time."""

    def __init__(
        self,
        *,
        resolution: int,
        submodule_dir: str | Path | None = None,
        model_dir: str | Path | None = None,
        dit_model: str = DEFAULT_SEEDVR2_DIT_MODEL,
        cuda_device: str | None = None,
        batch_size: int = 1,
        vae_tiled: bool = True,
        cache_models: bool = True,
        debug: bool = False,
    ) -> None:
        self.resolution = resolution
        self.submodule_dir = Path(submodule_dir).expanduser() if submodule_dir else default_seedvr2_submodule_dir()
        self.model_dir = Path(model_dir).expanduser() if model_dir else Path(DEFAULT_SEEDVR2_MODEL_DIR).expanduser()
        self.dit_model = dit_model
        self.cuda_device = cuda_device
        self.batch_size = batch_size
        self.vae_tiled = vae_tiled
        self.cache_models = cache_models
        self.debug = debug
        self._module: ModuleType | None = None
        self._downloaded = False
        self._runner_cache: dict[str, Any] | None = {} if cache_models else None

    def prepare(self) -> None:
        module = self._load_module()
        if not self._downloaded:
            vae_model = getattr(module, "DEFAULT_VAE", "ema_vae_fp16.safetensors")
            try:
                downloaded = module.download_weight(
                    dit_model=self.dit_model,
                    vae_model=vae_model,
                    model_dir=str(self.model_dir),
                    debug=getattr(module, "debug", None),
                )
            except SystemExit as exc:
                raise SeedVR2Unavailable(
                    f"SeedVR2 model download exited with code {_format_exit_code(exc)}"
                ) from exc
            except Exception as exc:
                raise SeedVR2Unavailable(
                    f"SeedVR2 model download failed: {_format_exception(exc)}"
                ) from exc
            if not downloaded:
                raise SeedVR2Unavailable(
                    f"SeedVR2 model download failed for {self.dit_model}; "
                    f"check network access and model cache {self.model_dir}"
                )
            self._downloaded = True

    def __call__(self, path: Path, output_path: Path) -> Path:
        self.prepare()
        module = self._load_module()
        args = self._build_args(path, output_path)
        try:
            frames = module.process_single_file(
                str(path),
                args,
                self._device_list(),
                output_path=str(output_path),
                format_auto_detected=False,
                runner_cache=self._runner_cache,
            )
        except SystemExit as exc:
            raise RuntimeError(
                f"SeedVR2 processing exited with code {_format_exit_code(exc)} for {path.name}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"SeedVR2 processing failed for {path.name}: {_format_exception(exc)}") from exc
        if frames <= 0:
            raise RuntimeError(f"SeedVR2 produced no output frames for {path.name}")
        if not output_path.exists():
            raise RuntimeError(f"SeedVR2 did not write expected output: {output_path}")
        return output_path

    def _load_module(self) -> ModuleType:
        if self._module is not None:
            return self._module

        cli_path = self.submodule_dir / "inference_cli.py"
        if not cli_path.exists():
            raise SeedVR2Unavailable(
                f"SeedVR2 submodule not found at {self.submodule_dir}; "
                "run `git submodule update --init --recursive third_party/seedvr2`"
            )

        module_name = f"_plk_seedvr2_inference_{abs(hash(str(cli_path.resolve())))}"
        spec = importlib.util.spec_from_file_location(module_name, cli_path)
        if spec is None or spec.loader is None:
            raise SeedVR2Unavailable(f"Could not import SeedVR2 CLI from {cli_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except SystemExit as exc:
            sys.modules.pop(module_name, None)
            raise SeedVR2Unavailable(
                f"SeedVR2 runtime import exited with code {_format_exit_code(exc)}"
            ) from exc
        except ModuleNotFoundError as exc:
            sys.modules.pop(module_name, None)
            raise SeedVR2Unavailable(
                f"SeedVR2 runtime dependency is missing: {exc.name}"
            ) from exc
        except ImportError as exc:
            sys.modules.pop(module_name, None)
            raise SeedVR2Unavailable(f"SeedVR2 runtime import failed: {exc}") from exc
        except Exception as exc:
            sys.modules.pop(module_name, None)
            raise SeedVR2Unavailable(f"SeedVR2 runtime is unavailable: {exc}") from exc

        debug = getattr(module, "debug", None)
        if debug is not None and hasattr(debug, "enabled"):
            debug.enabled = self.debug
        self._module = module
        return module

    def _build_args(self, path: Path, output_path: Path) -> argparse.Namespace:
        return argparse.Namespace(
            input=str(path),
            output=str(output_path),
            output_format="png",
            video_backend="opencv",
            use_10bit=False,
            model_dir=str(self.model_dir),
            dit_model=self.dit_model,
            resolution=self.resolution,
            max_resolution=0,
            batch_size=self.batch_size,
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
            cuda_device=self.cuda_device,
            dit_offload_device="none",
            vae_offload_device="none",
            tensor_offload_device="cpu",
            blocks_to_swap=0,
            swap_io_components=False,
            vae_encode_tiled=self.vae_tiled,
            vae_encode_tile_size=1024,
            vae_encode_tile_overlap=128,
            vae_decode_tiled=self.vae_tiled,
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
            cache_dit=self.cache_models,
            cache_vae=self.cache_models,
            debug=self.debug,
        )

    def _device_list(self) -> list[str]:
        if self.cuda_device:
            devices = [d.strip() for d in str(self.cuda_device).split(",") if d.strip()]
            if devices:
                return devices
        return ["0"]


def _format_exit_code(exc: SystemExit) -> str:
    return str(exc.code if exc.code is not None else 0)


def _format_exception(exc: BaseException) -> str:
    message = str(exc).strip()
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__
