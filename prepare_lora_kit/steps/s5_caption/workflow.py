"""Per-image caption workflow for Step 5."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ...cancellation import CancelCheck, CancelledRun, check_cancel
from ...interaction import InteractionProvider
from ...utils import report as rpt

from . import vlm
from .regions import make_region_captioner
from .reports import _save_failure_report
from .validation import clean_caption_for_mode


@dataclass
class CaptionWorkflowResult:
    captions: dict[str, str] = field(default_factory=dict)
    skipped_annotation: list[str] = field(default_factory=list)
    skip_all: bool = False


def caption_images(
    images: list[Path],
    *,
    output_dir: Path,
    overwrite: bool,
    enabled: set[str],
    provider: InteractionProvider,
    runtime: vlm.CaptionRuntime,
    concept_token: str | None,
    style_mode: bool,
    max_new_tokens: int,
    report_path: Path | None,
    cancel_check: CancelCheck | None,
) -> CaptionWorkflowResult:
    result = CaptionWorkflowResult()
    region_captioner = make_region_captioner(
        runtime=runtime,
        output_dir=output_dir,
        captions=result.captions,
        concept_token=concept_token,
        cancel_check=cancel_check,
    )

    for path in images:
        check_cancel(cancel_check)

        txt_path = output_dir / (path.stem + ".txt")

        if _load_existing_caption(path, txt_path, result.captions, overwrite):
            continue
        if _preserve_sidecar_when_captioning_disabled(path, txt_path, result.captions, enabled):
            continue

        annotations = _collect_annotations(
            path,
            enabled=enabled,
            provider=provider,
            region_captioner=region_captioner,
            result=result,
            cancel_check=cancel_check,
        )
        caption = _caption_full_image(
            path,
            annotations,
            images=images,
            enabled=enabled,
            result=result,
            runtime=runtime,
            concept_token=concept_token,
            max_new_tokens=max_new_tokens,
            report_path=report_path or (output_dir / "step5_report.json"),
            cancel_check=cancel_check,
        )
        _write_caption(
            path,
            txt_path,
            caption,
            result.captions,
            concept_token=concept_token,
            style_mode=style_mode,
            cancel_check=cancel_check,
        )

    return result


def _load_existing_caption(
    path: Path,
    txt_path: Path,
    captions: dict[str, str],
    overwrite: bool,
) -> bool:
    if not txt_path.exists() or overwrite:
        return False

    captions[str(path)] = txt_path.read_text(encoding="utf-8").strip()
    rpt.info(f"Skip (exists): {path.name}")
    return True


def _preserve_sidecar_when_captioning_disabled(
    path: Path,
    txt_path: Path,
    captions: dict[str, str],
    enabled: set[str],
) -> bool:
    if "s5_2_caption" in enabled:
        return False

    rpt.info(f"Caption substep disabled for {path.name}; preserving existing sidecar if present.")
    if txt_path.exists():
        captions[str(path)] = txt_path.read_text(encoding="utf-8").strip()
    return True


def _collect_annotations(
    path: Path,
    *,
    enabled: set[str],
    provider: InteractionProvider,
    region_captioner: Callable[[Any, dict[str, Any] | None], dict[str, str]],
    result: CaptionWorkflowResult,
    cancel_check: CancelCheck | None,
) -> list:
    if "s5_1_annotate" not in enabled or result.skip_all:
        annotations, skipped = [], True
    else:
        annotations, skipped, result.skip_all = provider.annotate_image(
            path,
            captioner=region_captioner,
        )

    check_cancel(cancel_check)
    if skipped:
        result.skipped_annotation.append(str(path))
    return annotations


def _caption_full_image(
    path: Path,
    annotations: list,
    *,
    images: list[Path],
    enabled: set[str],
    result: CaptionWorkflowResult,
    runtime: vlm.CaptionRuntime,
    concept_token: str | None,
    max_new_tokens: int,
    report_path: Path,
    cancel_check: CancelCheck | None,
) -> str:
    try:
        check_cancel(cancel_check)
        caption = runtime.caption_image(
            path,
            annotations,
            concept_token,
            max_new_tokens=max_new_tokens,
        )
        check_cancel(cancel_check)
        return caption
    except CancelledRun:
        raise
    except Exception as exc:
        _save_failure_report(
            report_path,
            images=images,
            captions=result.captions,
            skipped_annotation=result.skipped_annotation,
            runtime=runtime,
            error=f"VL captioning failed for {path.name}: {exc}",
            enabled=enabled,
        )
        raise RuntimeError(f"VL captioning failed for {path.name}: {exc}") from exc


def _write_caption(
    path: Path,
    txt_path: Path,
    caption: str,
    captions: dict[str, str],
    *,
    concept_token: str | None,
    style_mode: bool,
    cancel_check: CancelCheck | None,
) -> None:
    caption = clean_caption_for_mode(
        caption,
        path,
        concept_token,
        style_mode=style_mode,
    )

    check_cancel(cancel_check)
    txt_path.write_text(caption, encoding="utf-8")
    captions[str(path)] = caption
    rpt.ok(f"{path.name} → {caption[:80]}…" if len(caption) > 80 else f"{path.name} → {caption}")
