"""Deterministic mock runtime for CaptionStep (--mock)."""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from prepare_lora_kit.cancellation import check_cancel


def _mock_caption(
        working_dir: Path,
        output_dir: Path,
        *,
        concept_token: Optional[str],
        force: bool,
        enabled_substeps: list[str] | None = None,
        cancel_check=None,
        interaction=None,
) -> dict:
    from ..utils import image as img_utils
    from ..utils import report as rpt
    from ..interaction import annotate_dataset_via_images
    from ..steps.s5_caption.artifacts import (
        _is_bbox_artifact,
        _save_bbox_training_item,
        load_boxes_sidecar,
        save_boxes_sidecar,
    )

    rpt.step_header(5, "Caption — Mock Runtime")
    enabled = set(enabled_substeps or ["s5_1_annotate", "s5_2_caption", "s5_3_validate"])
    working_dir.mkdir(parents=True, exist_ok=True)
    images = [p for p in img_utils.iter_images(working_dir) if not _is_bbox_artifact(p)]
    token_prefix = f"{concept_token}, " if concept_token else ""

    # Resume: only images that still lack a caption need work (``force`` recaptions
    # everything). Already-captioned images and their hand-drawn boxes are left
    # untouched, mirroring steps/s5_caption/step.py.
    pending = [p for p in images if force or not p.with_suffix(".txt").exists()]
    pending_set = set(pending)

    # Mirror steps/s5_caption/regions.py::make_region_captioner but caption the
    # cropped region with deterministic mock text instead of a VLM, so the UI
    # "Caption selected box" button works end-to-end under --mock.
    def mock_region_captioner(crop, metadata=None):
        check_cancel(cancel_check)
        source_raw = (metadata or {}).get("source_path") or (metadata or {}).get("image_path")
        if not source_raw:
            raise ValueError("Region caption metadata missing source_path")
        source_path = Path(source_raw)
        text = f"mock region caption for {source_path.stem}"
        return _save_bbox_training_item(crop, source_path, output_dir, text, concept_token)

    captions: dict[str, str] = {}
    annotation_log: dict[str, list] = {}
    skipped_annotation: list[str] = []

    # Preserve already-captioned images so the report stays complete on a resume.
    for path in images:
        if path in pending_set:
            continue
        txt_path = path.with_suffix(".txt")
        if txt_path.exists():
            captions[str(path)] = txt_path.read_text(encoding="utf-8").strip()

    # Phase A — gather decisions via the same batch interaction the real step uses
    # (steps/s5_caption/workflow.py::gather_decisions), for the pending images only.
    # Headless/CLI mock has no provider, so every pending image captions with no
    # regions; a resume with nothing pending never pops an empty modal.
    if not pending or "s5_2_caption" not in enabled:
        decisions: dict[str, dict] = {}
    elif "s5_1_annotate" not in enabled or interaction is None:
        decisions = {str(p): {"annotations": [], "skipped": False} for p in pending}
    else:
        descriptors = [
            {
                "path": path,
                "name": path.name,
                "annotations": load_boxes_sidecar(path),
                "done": path.with_suffix(".txt").exists() and not force,
            }
            for path in pending
        ]
        annotate = getattr(interaction, "annotate_dataset", None)
        if annotate is not None:
            decisions, _skip_all = annotate(descriptors, captioner=mock_region_captioner)
        else:
            decisions, _skip_all = annotate_dataset_via_images(
                interaction, descriptors, captioner=mock_region_captioner,
            )

    # Phase B — caption each pending, non-skipped image with deterministic mock text.
    for path in pending:
        check_cancel(cancel_check)
        txt_path = path.with_suffix(".txt")
        decision = decisions.get(str(path))

        if "s5_2_caption" not in enabled:
            if txt_path.exists():
                captions[str(path)] = txt_path.read_text(encoding="utf-8").strip()
            continue

        if decision is None or decision.get("skipped"):
            if txt_path.exists() and not force:
                captions[str(path)] = txt_path.read_text(encoding="utf-8").strip()
                rpt.info(f"Skip (keep existing): {path.name}")
            skipped_annotation.append(str(path))
            continue

        annotations = decision.get("annotations") or []
        annotation_log[str(path)] = annotations
        if not annotations:
            skipped_annotation.append(str(path))
        save_boxes_sidecar(path, annotations)

        caption = f"{token_prefix}mock caption for {path.stem}".strip()
        txt_path.write_text(caption, encoding="utf-8")
        captions[str(path)] = caption
        rpt.ok(f"{path.name} -> {caption}")

    report = {
        "mock_runtime": True,
        "total": len(images),
        "captioned": len(captions),
        "annotations": annotation_log,
        "skipped_annotation": skipped_annotation,
        "missing_token": [],
        "short_captions": [],
        "long_captions": [],
        "spot_check_sample": [],
        "substeps": {
            "s5_1_annotate": {"enabled": "s5_1_annotate" in enabled},
            "s5_2_caption": {"enabled": "s5_2_caption" in enabled},
            "s5_3_validate": {"enabled": "s5_3_validate" in enabled},
        },
    }
    check_cancel(cancel_check)
    rpt.save_report(report, output_dir / "reports" / "CaptionStep_report.json")
    return report
