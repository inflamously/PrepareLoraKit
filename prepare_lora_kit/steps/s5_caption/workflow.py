"""Per-image caption workflow for Step 5."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ...interaction import annotate_dataset_via_images
from ...providers.interaction import InteractionProvider
from ...cancellation import CancelCheck, CancelledRun, check_cancel
from ...utils import report as rpt

from . import vlm
from .artifacts import _update_bbox_caption, load_boxes_sidecar, save_boxes_sidecar
from .reports import _save_failure_report
from .validation import clean_caption_for_mode


@dataclass
class CaptionWorkflowResult:
    captions: dict[str, str] = field(default_factory=dict)
    skipped_annotation: list[str] = field(default_factory=list)
    skip_all: bool = False


def gather_decisions(
        images: list[Path],
        *,
        txt_paths: dict[Path, Path],
        overwrite: bool,
        enabled: set[str],
        provider: InteractionProvider | None,
        region_captioner: Callable[[Any, dict[str, Any] | None], dict[str, str]],
        result: CaptionWorkflowResult,
        cancel_check: CancelCheck | None,
) -> dict[str, dict]:
    """Phase A: collect per-image caption decisions in one batch interaction.

    Returns ``{str(path): {"annotations": [...], "skipped": bool}}``. ``skipped``
    means "do not caption this image" (keep any existing caption). Images absent
    from the map are treated the same as skipped by :func:`resolve_decision`.
    """
    # Captioning disabled → no interaction; sidecars are preserved in phase B.
    if "s5_2_caption" not in enabled:
        return {}
    # Annotation disabled or headless → caption every image with no regions
    # (mirrors the prior per-image behavior of skipping the annotator only).
    if "s5_1_annotate" not in enabled or provider is None:
        return {str(path): {"annotations": [], "skipped": False} for path in images}

    descriptors = [
        {
            "path": path,
            "name": path.name,
            "annotations": load_boxes_sidecar(path),
            "done": txt_paths[path].exists() and not overwrite,
        }
        for path in images
    ]
    annotate = getattr(provider, "annotate_dataset", None)
    if annotate is not None:
        decisions, result.skip_all = annotate(descriptors, captioner=region_captioner)
    else:
        decisions, result.skip_all = annotate_dataset_via_images(
            provider, descriptors, captioner=region_captioner,
        )
    check_cancel(cancel_check)
    return decisions


def resolve_decision(
        path: Path,
        txt_path: Path,
        decision: dict | None,
        *,
        overwrite: bool,
        enabled: set[str],
        result: CaptionWorkflowResult,
) -> list | None:
    """Decide phase B's action for one image.

    Returns the annotation list to caption with, or ``None`` to skip captioning
    (caption substep off, an explicit skip, or no decision) — in which case any
    existing sidecar caption is kept so reports stay complete.
    """
    if "s5_2_caption" not in enabled:
        rpt.info(f"Caption substep disabled for {path.name}; preserving existing sidecar if present.")
        if txt_path.exists():
            result.captions[str(path)] = txt_path.read_text(encoding="utf-8").strip()
        return None

    if decision is None or decision.get("skipped"):
        if txt_path.exists() and not overwrite:
            result.captions[str(path)] = txt_path.read_text(encoding="utf-8").strip()
            rpt.info(f"Skip (keep existing): {path.name}")
        result.skipped_annotation.append(str(path))
        return None

    annotations = decision.get("annotations") or []
    if not annotations:
        # Captioned, but no regions were drawn — recorded like a skipped annotation.
        result.skipped_annotation.append(str(path))
    return annotations


def _persist_region_caption_edits(
        annotations: list,
        captions: dict[str, str],
        *,
        concept_token: str | None,
) -> None:
    """Write back edits made to captioned regions before the modal was submitted.

    A region captioned in the UI carries a ``sidecar_path`` (and ``crop_path``); its
    label may have been edited after captioning. Rewrite each such sidecar from the
    submitted label so the on-disk training caption reflects the edit, and keep the
    in-memory ``captions`` map (keyed by crop path) consistent for reporting.
    """
    for ann in annotations:
        if not isinstance(ann, dict):
            continue
        sidecar = ann.get("sidecar_path")
        label = (ann.get("label") or "").strip()
        if not sidecar or not label:
            continue
        final = _update_bbox_caption(Path(sidecar), label, concept_token)
        crop_path = ann.get("crop_path")
        if crop_path:
            captions[crop_path] = final


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
