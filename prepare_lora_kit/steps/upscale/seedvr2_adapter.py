"""Subprocess adapter for the optional SeedVR2 submodule."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .seedvr2_catalog import DEFAULT_SEEDVR2_DIT_MODEL

DEFAULT_SEEDVR2_MODEL_DIR = "~/.cache/prepare_lora_kit/seedvr2"
SEEDVR2_MODEL_RESIDENCY_MODES = ("auto", "gpu", "cpu")


class SeedVR2Unavailable(RuntimeError):
    """Raised when the optional SeedVR2 runtime cannot be used."""


def default_seedvr2_submodule_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "third_party" / "seedvr2"


class SeedVR2Upscaler:
    """Run SeedVR2 in one isolated worker process for a batch of images."""

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
        model_residency: str = "auto",
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
        self.model_residency = model_residency
        self.debug = debug

    def prepare(self) -> None:
        cli_path = self.submodule_dir / "inference_cli.py"
        if not cli_path.exists():
            raise SeedVR2Unavailable(
                f"SeedVR2 submodule not found at {self.submodule_dir}; "
                "run `git submodule update --init --recursive third_party/seedvr2`"
            )
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def __call__(self, path: Path, output_path: Path) -> Path:
        failures = self.process_many({path: output_path})
        if failures:
            raise RuntimeError(failures[str(path)])
        return output_path

    def process_many(
        self,
        outputs_by_source: Mapping[Path, Path],
        *,
        sources_by_path: Mapping[Path, Path] | None = None,
        cancel_check=None,
    ) -> dict[str, str]:
        self.prepare()
        if not outputs_by_source:
            return {}

        request = self._build_request(outputs_by_source, sources_by_path)
        response = self._run_worker(request, cancel_check=cancel_check)
        for warning in response.get("warnings") or []:
            from ...utils import report as rpt

            rpt.warn(str(warning))
        failed = response.get("failed") or {}
        return {str(path): str(reason) for path, reason in failed.items()}

    def _build_request(
        self,
        outputs_by_source: Mapping[Path, Path],
        sources_by_path: Mapping[Path, Path] | None = None,
    ) -> dict[str, Any]:
        sources_by_path = sources_by_path or {}
        return {
            "resolution": self.resolution,
            "submodule_dir": str(self.submodule_dir),
            "model_dir": str(self.model_dir),
            "dit_model": self.dit_model,
            "cuda_device": self.cuda_device,
            "batch_size": self.batch_size,
            "vae_tiled": self.vae_tiled,
            "cache_models": self.cache_models,
            "model_residency": self.model_residency,
            "debug": self.debug,
            "items": [
                {
                    "key": str(key),
                    "source": str(sources_by_path.get(key, key)),
                    "output": str(output),
                }
                for key, output in outputs_by_source.items()
            ],
        }

    def _run_worker(self, request: dict[str, Any], *, cancel_check=None) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="plk_seedvr2_") as tmp:
            request_path = Path(tmp) / "request.json"
            response_path = Path(tmp) / "response.json"
            request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
            cmd = [
                sys.executable,
                "-m",
                "prepare_lora_kit.steps.upscale.seedvr2_worker",
                "--request",
                str(request_path),
                "--response",
                str(response_path),
            ]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            output_tail: list[str] = []
            reader = threading.Thread(
                target=_forward_output,
                args=(process.stdout, output_tail),
                daemon=True,
            )
            reader.start()
            try:
                while process.poll() is None:
                    if cancel_check is not None:
                        cancel_check()
                    try:
                        process.wait(timeout=0.25)
                    except subprocess.TimeoutExpired:
                        continue
            except BaseException:
                _terminate_process(process)
                raise
            finally:
                reader.join(timeout=2)

            if process.returncode != 0:
                response = _read_response(response_path)
                message = str(response.get("error") or "").strip()
                if not message:
                    message = f"SeedVR2 worker exited with code {process.returncode}"
                if output_tail:
                    message = f"{message}; recent output: {' | '.join(output_tail[-5:])}"
                raise SeedVR2Unavailable(message)

            response = _read_response(response_path)
            if response.get("status") != "ok":
                raise SeedVR2Unavailable(str(response.get("error") or "SeedVR2 worker failed"))
            return response


def _forward_output(pipe, output_tail: list[str]) -> None:
    if pipe is None:
        return
    try:
        for line in pipe:
            clean = line.rstrip()
            if clean:
                print(clean)
                output_tail.append(clean)
                del output_tail[:-20]
    finally:
        pipe.close()


def _terminate_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _read_response(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
