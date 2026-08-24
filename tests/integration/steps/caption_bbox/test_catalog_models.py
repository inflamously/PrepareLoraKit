"""Opt-in smoke tests for every supported caption model other than Qwen3.8."""
import pytest

from tests.integration.steps.caption_bbox.model_smoke import (
    CaptionModelCase,
    opt_in,
    run_prompted_model_smoke,
)

_CASES = (
    CaptionModelCase(
        "Qwen/Qwen3-VL-2B-Instruct",
        "PLK_RUN_QWEN3_VL_2B_INTEGRATION",
        "qwen3-vl-2b",
    ),
    CaptionModelCase(
        "Qwen/Qwen3-VL-4B-Instruct",
        "PLK_RUN_QWEN3_VL_4B_INTEGRATION",
        "qwen3-vl-4b",
    ),
    CaptionModelCase(
        "Qwen/Qwen3-VL-8B-Instruct",
        "PLK_RUN_QWEN3_VL_8B_INTEGRATION",
        "qwen3-vl-8b",
    ),
    CaptionModelCase(
        "Qwen/Qwen2.5-VL-3B-Instruct",
        "PLK_RUN_QWEN25_VL_3B_INTEGRATION",
        "qwen25-vl-3b",
    ),
    CaptionModelCase(
        "Qwen/Qwen2.5-VL-7B-Instruct",
        "PLK_RUN_QWEN25_VL_7B_INTEGRATION",
        "qwen25-vl-7b",
    ),
    CaptionModelCase(
        "Qwen/Qwen2-VL-7B-Instruct",
        "PLK_RUN_QWEN2_VL_7B_INTEGRATION",
        "qwen2-vl-7b",
    ),
    CaptionModelCase(
        "fancyfeast/llama-joycaption-beta-one-hf-llava",
        "PLK_RUN_JOYCAPTION_INTEGRATION",
        "joycaption-beta-one",
    ),
)


@pytest.mark.parametrize(
    "case",
    [pytest.param(case, marks=opt_in(case), id=case.test_id) for case in _CASES],
)
def test_catalog_caption_model_multimodal_runtime(case):
    run_prompted_model_smoke(case)
