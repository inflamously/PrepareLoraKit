"""Real Qwen3.8 smoke test; opt in because it downloads and loads a 27B model.

Run from a CUDA environment that already satisfies the caption dependencies:

    PLK_RUN_QWEN38_INTEGRATION=1 \
    PLK_QWEN38_QUANTIZATION=8bit \
    pytest -q -s tests/integration/steps/caption_bbox/test_qwen38.py

Use ``4bit`` for a smaller card. ``-s`` displays load/runtime diagnostics and
the assistant content PLK extracted from the raw generation.
"""
from tests.integration.steps.caption_bbox.model_smoke import (
    CaptionModelCase,
    opt_in,
    run_prompted_model_smoke,
)

_QWEN38 = CaptionModelCase(
    model_id="Qwen/Qwen3.8-27B",
    env_flag="PLK_RUN_QWEN38_INTEGRATION",
    test_id="qwen38-27b",
    default_quantization="8bit",
    quantization_env="PLK_QWEN38_QUANTIZATION",
)


@opt_in(_QWEN38)
def test_qwen38_multimodal_runtime_generates_hello_world():
    run_prompted_model_smoke(_QWEN38)
