"""Real Qwen3.8 smoke test; opt in because it downloads and loads a 27B model.

Run from a CUDA environment that already satisfies the caption dependencies:

    PLK_RUN_QWEN38_INTEGRATION=1 \
    PLK_QWEN38_QUANTIZATION=8bit \
    pytest -q -s tests/integration/test_qwen38_caption.py

Use ``4bit`` for a smaller card. ``-s`` displays the raw token decode and the
assistant content PLK extracted from it, which makes thinking/parser failures
visible instead of reducing them to an unhelpful assertion.
"""
from __future__ import annotations

import json
import os
import re
from importlib import metadata

import pytest

from prepare_lora_kit.steps.caption_bbox import vlm

_MODEL_ID = "Qwen/Qwen3.8-27B"
_RUN_INTEGRATION = os.environ.get("PLK_RUN_QWEN38_INTEGRATION") == "1"

pytestmark = pytest.mark.skipif(
    not _RUN_INTEGRATION,
    reason="set PLK_RUN_QWEN38_INTEGRATION=1 to load the real 27B caption model",
)


def _quantization() -> str:
    value = os.environ.get("PLK_QWEN38_QUANTIZATION", "8bit").strip().lower()
    if value not in {"4bit", "8bit", "none"}:
        pytest.fail("PLK_QWEN38_QUANTIZATION must be 4bit, 8bit, or none")
    return value


def _hello_world_generation(loaded, image):
    import torch

    prompt = (
        "Ignore the image contents. Reply with exactly these two lowercase words: "
        "hello world. Do not explain and do not add punctuation."
    )
    messages = [{
        "role": "user",
        "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}],
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


def test_qwen38_multimodal_runtime_generates_hello_world():
    import torch
    import transformers
    from PIL import Image

    if not torch.cuda.is_available():
        pytest.skip("Qwen3.8 integration test requires CUDA")

    quantization = _quantization()
    free_vram, total_vram = torch.cuda.mem_get_info()
    load_diagnostic = {
        "model_id": _MODEL_ID,
        "transformers": transformers.__version__,
        "torch": torch.__version__,
        "accelerate": metadata.version("accelerate"),
        "bitsandbytes": metadata.version("bitsandbytes"),
        "quantization": quantization,
        "gpu": torch.cuda.get_device_name(0),
        "free_vram_gb": round(free_vram / 1024 ** 3, 2),
        "total_vram_gb": round(total_vram / 1024 ** 3, 2),
    }
    try:
        loaded = vlm._load(
            _MODEL_ID,
            "image-text-to-text",
            quantization,
            "bfloat16",
            64 * 64,
        )
    except Exception as exc:
        load_diagnostic["load_error_type"] = type(exc).__name__
        load_diagnostic["load_error"] = str(exc)
        print("QWEN38_LOAD_DIAGNOSTIC=" + json.dumps(
            load_diagnostic, ensure_ascii=False, indent=2
        ))
        raise
    try:
        input_keys, raw, parsed = _hello_world_generation(
            loaded, Image.new("RGB", (64, 64), color=(180, 30, 30))
        )
        diagnostic = {
            "model_id": _MODEL_ID,
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
        print("QWEN38_DIAGNOSTIC=" + json.dumps(diagnostic, ensure_ascii=False, indent=2))

        normalized = " ".join(re.findall(r"[a-z]+", parsed.lower()))
        assert normalized == "hello world", json.dumps(diagnostic, ensure_ascii=False)
    finally:
        vlm.unload()
