"""Shared real-model smoke harness for caption VLM integration tests."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from importlib import metadata

import pytest

from prepare_lora_kit.steps.caption_bbox import vlm

_QUANTIZATIONS = {"auto", "4bit", "8bit", "none"}
_PROMPT = (
    "Ignore the image contents. Reply with exactly these two lowercase words: "
    "hello world. Do not explain and do not add punctuation."
)


@dataclass(frozen=True)
class CaptionModelCase:
    """One downloadable caption model and the environment flag that opts into it."""

    model_id: str
    env_flag: str
    test_id: str
    default_quantization: str = "auto"
    quantization_env: str = "PLK_CAPTION_INTEGRATION_QUANTIZATION"

    @property
    def enabled(self) -> bool:
        return os.environ.get(self.env_flag) == "1"

    def quantization(self) -> str:
        value = os.environ.get(self.quantization_env, self.default_quantization).strip().lower()
        if value not in _QUANTIZATIONS:
            pytest.fail(
                f"{self.quantization_env} must be auto, 4bit, 8bit, or none; got {value!r}"
            )
        return value


def opt_in(case: CaptionModelCase):
    """Skip a real-model case unless its dedicated environment flag is enabled."""
    return pytest.mark.skipif(
        not case.enabled,
        reason=f"set {case.env_flag}=1 to load the real caption model",
    )


def _prompted_generation(loaded, image):
    import torch

    messages = [{
        "role": "user",
        "content": [{"type": "image", "image": image}, {"type": "text", "text": _PROMPT}],
    }]
    inputs = vlm._prepare_prompted_inputs(loaded, messages, image)
    prefix_ids = inputs["input_ids"][0]
    input_keys = sorted(inputs)
    inputs = vlm._to_device(inputs, vlm._input_device(loaded.model))
    try:
        with torch.no_grad():
            output = loaded.model.generate(
                **inputs,
                max_new_tokens=32,
                do_sample=False,
                temperature=None,
                top_p=None,
            )
        generated_ids = output[0][inputs["input_ids"].shape[1]:]
        raw = loaded.processor.decode(generated_ids, skip_special_tokens=False)
        parsed = vlm._decode_prompted_response(loaded, generated_ids, prefix_ids)
        return input_keys, raw, vlm._finalize_caption(parsed)
    finally:
        del inputs
        vlm._clear_cuda(torch)


def _dependency_version(package: str) -> str | None:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return None


def _load_diagnostic(case: CaptionModelCase, quantization: str, torch, transformers) -> dict:
    free_vram, total_vram = torch.cuda.mem_get_info()
    return {
        "model_id": case.model_id,
        "transformers": transformers.__version__,
        "torch": torch.__version__,
        "accelerate": _dependency_version("accelerate"),
        "bitsandbytes": _dependency_version("bitsandbytes"),
        "quantization": quantization,
        "gpu": torch.cuda.get_device_name(0),
        "free_vram_gb": round(free_vram / 1024 ** 3, 2),
        "total_vram_gb": round(total_vram / 1024 ** 3, 2),
    }


def _result_diagnostic(case: CaptionModelCase, loaded, input_keys, raw, parsed, torch,
                       transformers) -> dict:
    return {
        "model_id": case.model_id,
        "model_class": type(loaded.model).__name__,
        "model_type": getattr(loaded.model.config, "model_type", None),
        "processor_class": type(loaded.processor).__name__,
        "transformers": transformers.__version__,
        "quantization": loaded.quantization,
        "device": loaded.device,
        "gpu": torch.cuda.get_device_name(0),
        "input_keys": input_keys,
        "raw_generation": raw,
        "parsed_caption": parsed,
    }


def run_prompted_model_smoke(case: CaptionModelCase) -> None:
    """Load one real VLM and verify its multimodal prompt path and response parser."""
    import torch
    import transformers
    from PIL import Image

    if not torch.cuda.is_available():
        pytest.skip("real caption-model integration tests require CUDA")

    quantization = case.quantization()
    load_diagnostic = _load_diagnostic(case, quantization, torch, transformers)
    try:
        loaded = vlm._load(
            case.model_id,
            "image-text-to-text",
            quantization,
            "bfloat16",
            64 * 64,
        )
    except Exception as exc:
        load_diagnostic["load_error_type"] = type(exc).__name__
        load_diagnostic["load_error"] = str(exc)
        print("CAPTION_MODEL_LOAD_DIAGNOSTIC=" + json.dumps(
            load_diagnostic, ensure_ascii=False, indent=2,
        ))
        raise

    try:
        input_keys, raw, parsed = _prompted_generation(
            loaded, Image.new("RGB", (64, 64), color=(180, 30, 30)),
        )
        diagnostic = _result_diagnostic(
            case, loaded, input_keys, raw, parsed, torch, transformers,
        )
        print("CAPTION_MODEL_DIAGNOSTIC=" + json.dumps(
            diagnostic, ensure_ascii=False, indent=2,
        ))

        normalized = " ".join(re.findall(r"[a-z]+", parsed.lower()))
        assert normalized == "hello world", json.dumps(diagnostic, ensure_ascii=False)
    finally:
        vlm.unload()
