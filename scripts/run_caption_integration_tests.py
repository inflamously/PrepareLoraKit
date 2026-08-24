#!/usr/bin/env python3
"""Run every opt-in caption-model integration test in an isolated process."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TEST_ROOT = "tests/integration/steps/caption_bbox"


@dataclass(frozen=True)
class IntegrationRun:
    label: str
    node_id: str
    env_flag: str
    quantization_env: str = "PLK_CAPTION_INTEGRATION_QUANTIZATION"


_RUNS = (
    IntegrationRun(
        "Qwen3-VL 2B",
        f"{_TEST_ROOT}/test_catalog_models.py::"
        "test_catalog_caption_model_multimodal_runtime[qwen3-vl-2b]",
        "PLK_RUN_QWEN3_VL_2B_INTEGRATION",
    ),
    IntegrationRun(
        "Qwen3-VL 4B",
        f"{_TEST_ROOT}/test_catalog_models.py::"
        "test_catalog_caption_model_multimodal_runtime[qwen3-vl-4b]",
        "PLK_RUN_QWEN3_VL_4B_INTEGRATION",
    ),
    IntegrationRun(
        "Qwen3-VL 8B",
        f"{_TEST_ROOT}/test_catalog_models.py::"
        "test_catalog_caption_model_multimodal_runtime[qwen3-vl-8b]",
        "PLK_RUN_QWEN3_VL_8B_INTEGRATION",
    ),
    IntegrationRun(
        "Qwen2.5-VL 3B",
        f"{_TEST_ROOT}/test_catalog_models.py::"
        "test_catalog_caption_model_multimodal_runtime[qwen25-vl-3b]",
        "PLK_RUN_QWEN25_VL_3B_INTEGRATION",
    ),
    IntegrationRun(
        "Qwen2.5-VL 7B",
        f"{_TEST_ROOT}/test_catalog_models.py::"
        "test_catalog_caption_model_multimodal_runtime[qwen25-vl-7b]",
        "PLK_RUN_QWEN25_VL_7B_INTEGRATION",
    ),
    IntegrationRun(
        "Qwen2-VL 7B",
        f"{_TEST_ROOT}/test_catalog_models.py::"
        "test_catalog_caption_model_multimodal_runtime[qwen2-vl-7b]",
        "PLK_RUN_QWEN2_VL_7B_INTEGRATION",
    ),
    IntegrationRun(
        "JoyCaption Beta One",
        f"{_TEST_ROOT}/test_catalog_models.py::"
        "test_catalog_caption_model_multimodal_runtime[joycaption-beta-one]",
        "PLK_RUN_JOYCAPTION_INTEGRATION",
    ),
    IntegrationRun(
        "Qwen3.8 27B",
        f"{_TEST_ROOT}/test_qwen38.py::"
        "test_qwen38_multimodal_runtime_generates_hello_world",
        "PLK_RUN_QWEN38_INTEGRATION",
        "PLK_QWEN38_QUANTIZATION",
    ),
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run every real caption-model integration test sequentially. Each test gets a "
            "fresh Python process so model VRAM is fully released between runs."
        ),
    )
    parser.add_argument(
        "--quantization",
        choices=("auto", "4bit", "8bit", "none"),
        default="8bit",
        help="Quantization used for every model (default: 8bit).",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Extra pytest arguments after --, for example: -- --maxfail=1",
    )
    return parser


def _pytest_args(values: list[str]) -> list[str]:
    if values and values[0] == "--":
        return values[1:]
    return values


def _run_one(run: IntegrationRun, quantization: str, pytest_args: list[str]) -> int:
    env = os.environ.copy()
    env[run.env_flag] = "1"
    env[run.quantization_env] = quantization
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-s",
        *pytest_args,
        run.node_id,
    ]
    completed = subprocess.run(command, cwd=_REPO_ROOT, env=env, check=False)
    return completed.returncode


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    pytest_args = _pytest_args(args.pytest_args)
    failures: list[str] = []

    for index, run in enumerate(_RUNS, start=1):
        print(f"\n[{index}/{len(_RUNS)}] {run.label}", flush=True)
        if _run_one(run, args.quantization, pytest_args):
            failures.append(run.label)

    if failures:
        print("\nFailed caption integrations: " + ", ".join(failures), file=sys.stderr)
        return 1

    print(f"\nAll {len(_RUNS)} caption-model integrations passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
