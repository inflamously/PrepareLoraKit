"""Caption every case of a suite with each variant, recording what each pass did."""
from __future__ import annotations

import dataclasses
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

from prepare_lora_kit.caption_bench import store
from prepare_lora_kit.caption_bench.store import BenchRun, CaseResult
from prepare_lora_kit.caption_bench.suite import BenchCase, BenchSuite
from prepare_lora_kit.caption_bench.variants import BenchVariant
from prepare_lora_kit.pipeline.configs import CaptionBboxConfig
from prepare_lora_kit.report import reporter
from prepare_lora_kit.steps.caption_bbox.validation import clean_caption_for_mode


class BenchRuntime(Protocol):
    """The slice of ``vlm.CaptionRuntime`` the benchmark drives."""

    pass_counts: dict[str, int]

    @property
    def metadata(self) -> dict[str, Any]: ...

    def caption_image(
            self, image_path: Any, annotations: list[dict], concept_token: str | None,
            *, max_new_tokens: int = ..., trace: dict[str, Any] | None = ...,
    ) -> str: ...

    def unload(self) -> None: ...


RuntimeFactory = Callable[[CaptionBboxConfig], BenchRuntime]


def real_runtime_factory(config: CaptionBboxConfig) -> BenchRuntime:
    from prepare_lora_kit.steps.caption_bbox.real import make_caption_runtime

    return make_caption_runtime(config)


def _model_key(config: CaptionBboxConfig) -> tuple:
    """Settings that decide which weights are loaded; prompts and strategy do not."""
    return (config.caption_model_id, config.caption_model_task,
            config.quantization, config.dtype)


class CaptionBenchRunner:
    """Runs variants over one suite.

    A variant whose model matches the previous one reuses the loaded weights (the
    runtime's module-level cache keeps them), so comparing prompt variants costs one
    model load, not one per variant.
    """

    def __init__(
            self,
            suite: BenchSuite,
            *,
            runtime_factory: RuntimeFactory = real_runtime_factory,
            git_commit: Callable[[], str | None] = store.git_commit,
            now: Callable[[], datetime] = store.utc_now,
            on_case: Callable[[BenchVariant, BenchCase, CaseResult], None] | None = None,
    ) -> None:
        self.suite = suite
        self._factory = runtime_factory
        self._git_commit = git_commit
        self._now = now
        self._on_case = on_case

    def run(self, variants: list[BenchVariant]) -> list[BenchRun]:
        runs: list[BenchRun] = []
        runtime: BenchRuntime | None = None
        loaded_key: tuple | None = None
        try:
            for variant in variants:
                key = _model_key(variant.config)
                if runtime is not None and key != loaded_key:
                    runtime.unload()
                runtime = self._factory(variant.config)
                loaded_key = key
                runs.append(self._run_variant(variant, runtime))
        finally:
            if runtime is not None:
                runtime.unload()
        return runs

    def _run_variant(self, variant: BenchVariant, runtime: BenchRuntime) -> BenchRun:
        created = self._now()
        results = []
        for case in self.suite.cases:
            result = self._run_case(variant, runtime, case)
            results.append(result)
            if self._on_case is not None:
                self._on_case(variant, case, result)
        return BenchRun(
            run_id=store.make_run_id(created, variant.name),
            variant=variant.name,
            suite=self.suite.name,
            created_at=created.isoformat(),
            git_commit=self._git_commit(),
            model=dict(runtime.metadata),
            config=dataclasses.asdict(variant.config),
            results=results,
        )

    def _run_case(
            self, variant: BenchVariant, runtime: BenchRuntime, case: BenchCase,
    ) -> CaseResult:
        before = dict(runtime.pass_counts)
        trace: dict[str, Any] = {}
        started = time.perf_counter()
        try:
            raw = runtime.caption_image(
                case.image, case.annotations, case.concept_token,
                max_new_tokens=variant.config.max_new_tokens, trace=trace,
            )
        except Exception as exc:
            reporter.warn(f"[{variant.name}] {case.name}: captioning failed: {exc}")
            return CaseResult(
                image=case.rel_path, caption="", trace=trace,
                seconds=round(time.perf_counter() - started, 3), error=str(exc),
            )
        seconds = round(time.perf_counter() - started, 3)
        # Exactly the cleanup the step applies before writing the .txt.
        caption = clean_caption_for_mode(
            raw, case.image, case.concept_token,
            style_mode=not case.concept_token, annotations=case.annotations,
        )
        return CaseResult(
            image=case.rel_path,
            caption=caption,
            raw_caption=raw,
            trace=trace,
            passes=_pass_delta(before, runtime.pass_counts),
            seconds=seconds,
            words=len(caption.split()),
        )


def _pass_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    delta = {stage: count - before.get(stage, 0) for stage, count in after.items()}
    return {stage: count for stage, count in delta.items() if count}
