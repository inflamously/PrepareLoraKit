"""Shared orchestration for CaptionBboxStep.

``CaptionStep`` owns the whole per-image pipeline — output prep, resume, the batch
annotation interaction, the caption loop, validation, and reporting — and defers
only the parts that differ between a real VLM run and the deterministic ``--mock``
runtime to a handful of hooks. ``RealCaptionStep`` (``real.py``) and
``MockCaptionStep`` (``mock.py``) subclass it; nothing else re-implements the flow.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from prepare_lora_kit.cancellation import CancelCheck, check_cancel
from prepare_lora_kit.providers.interaction import InteractionProvider
from prepare_lora_kit.report import reporter
from prepare_lora_kit.project.pipeline.substeps import substep_ids_for
from prepare_lora_kit.utils import image as img_utils

from prepare_lora_kit.steps.caption_bbox.artifacts import _is_bbox_artifact, save_boxes_sidecar
from prepare_lora_kit.steps.caption_bbox.regions import make_region_captioner
from prepare_lora_kit.steps.caption_bbox.reports import (
    _REPORT_NAME,
    build_success_report,
    save_success_report,
)
from prepare_lora_kit.steps.caption_bbox.validation import render_spot_check, validate_captions
from prepare_lora_kit.steps.caption_bbox.workflow import (
    CaptionWorkflowResult,
    _persist_region_caption_edits,
    _write_caption,
    gather_decisions,
    resolve_decision,
)


class CaptionStep(ABC):
    """Template-method base for the captioning step."""

    #: Header line shown when the step starts.
    HEADER = "Caption — Bbox Annotation"
    #: Whether this step reports itself as a ``--mock`` runtime.
    mock_runtime = False

    def __init__(
            self,
            dataset_dir: Path,
            *,
            concept_token: str | None = None,
            output_dir: Path | None = None,
            spot_check_pct: float = 0.10,
            overwrite: bool = False,
            report_path: Path | None = None,
            max_new_tokens: int = 200,
            interaction: InteractionProvider | None = None,
            enabled_substeps: list[str] | None = None,
            cancel_check: CancelCheck | None = None,
    ) -> None:
        self.dataset_dir = dataset_dir
        self.concept_token = concept_token
        self.output_dir = output_dir or dataset_dir
        self.spot_check_pct = spot_check_pct
        self.overwrite = overwrite
        self.report_path = report_path
        self.max_new_tokens = max_new_tokens
        self.interaction = interaction
        self.cancel_check = cancel_check
        self.style_mode = not concept_token
        self.enabled = set(enabled_substeps or substep_ids_for("CaptionBboxStep"))

    # ── Hooks the subclasses fill in ────────────────────────────────────────────

    @abstractmethod
    def caption_full_image(
            self,
            path: Path,
            annotations: list,
            *,
            images: list[Path],
            result: CaptionWorkflowResult,
            output_dir: Path,
    ) -> str:
        """Produce the full-image caption text for one image."""

    @abstractmethod
    def _region_caption_fn(self, crop: Any, source_path: Path) -> str:
        """Produce the raw caption text for a single drawn region crop."""

    def prepare_runtime(self, needs_captioning: bool) -> None:
        """Validate/load the caption runtime before the loop (no-op by default)."""

    def teardown(self) -> None:
        """Release the caption runtime after the loop (no-op by default)."""

    def report_model_metadata(self) -> dict[str, Any]:
        """Model metadata recorded in the report."""
        return {}

    def report_status(self) -> dict[str, Any]:
        """Last runtime status snapshot recorded in the report."""
        return {}

    def validate(
            self,
            captions: dict[str, str],
    ) -> tuple[list[str], list[str], list[str], list[tuple[str, str]]]:
        """Run caption QA + spot check. Returns (missing_token, short, long, sample)."""
        missing_token, short, long_ = validate_captions(
            captions,
            self.concept_token,
            style_mode=self.style_mode,
            enabled=self.enabled,
            cancel_check=self.cancel_check,
        )
        sample = render_spot_check(
            captions,
            self.spot_check_pct,
            enabled=self.enabled,
            cancel_check=self.cancel_check,
        )
        return missing_token, short, long_, sample

    # ── Template method ─────────────────────────────────────────────────────────

    def run(self) -> dict:
        reporter.step_header(self.HEADER)
        output_dir = self._prepare_output_dir()
        all_images, images = self._collect_source_images()
        if not all_images:
            reporter.warn(f"No images in {self.dataset_dir}")
            return {}

        self._log_caption_mode(images)

        check_cancel(self.cancel_check)
        img_utils.materialize(all_images, self.dataset_dir, output_dir)

        # Resume: only images that still lack a caption need work (``overwrite`` — set
        # by --force — recaptions everything). When nothing is pending we skip loading
        # any runtime entirely and rebuild the report from the on-disk captions.
        txt_paths, pending = self._resolve_pending(images, output_dir)
        needs_captioning = bool(pending) and "caption_images" in self.enabled
        self.prepare_runtime(needs_captioning)

        try:
            result = self._caption_dataset(
                images,
                pending=pending,
                txt_paths=txt_paths,
                output_dir=output_dir,
            )
            return self._validate_and_save_success(images, result, output_dir=output_dir)
        finally:
            self.teardown()

    def _caption_dataset(
            self,
            images: list[Path],
            *,
            pending: list[Path],
            txt_paths: dict[Path, Path],
            output_dir: Path,
    ) -> CaptionWorkflowResult:
        result = CaptionWorkflowResult()
        region_captioner = make_region_captioner(
            caption_fn=self._region_caption_fn,
            output_dir=output_dir,
            captions=result.captions,
            concept_token=self.concept_token,
            cancel_check=self.cancel_check,
        )

        # Resume: leave already-captioned images (and their hand-drawn boxes)
        # untouched, but load their captions into the report so it stays complete.
        pending_set = set(pending)
        for path in images:
            if path in pending_set:
                continue
            txt_path = txt_paths[path]
            if txt_path.exists():
                result.captions[str(path)] = txt_path.read_text(encoding="utf-8").strip()

        # Phase A — one batch annotation interaction covering the pending images only.
        decisions = gather_decisions(
            pending,
            txt_paths=txt_paths,
            overwrite=self.overwrite,
            enabled=self.enabled,
            provider=self.interaction,
            region_captioner=region_captioner,
            result=result,
            cancel_check=self.cancel_check,
        ) if pending else {}

        # Phase B — caption each pending, non-skipped image with its annotations.
        for path in pending:
            check_cancel(self.cancel_check)
            txt_path = txt_paths[path]
            txt_path.parent.mkdir(parents=True, exist_ok=True)

            annotations = resolve_decision(
                path,
                txt_path,
                decisions.get(str(path)),
                overwrite=self.overwrite,
                enabled=self.enabled,
                result=result,
            )
            if annotations is None:
                continue

            _persist_region_caption_edits(
                annotations,
                result.captions,
                concept_token=self.concept_token,
            )
            save_boxes_sidecar(path, annotations)
            caption = self.caption_full_image(
                path,
                annotations,
                images=images,
                result=result,
                output_dir=output_dir,
            )
            _write_caption(
                path,
                txt_path,
                caption,
                result.captions,
                concept_token=self.concept_token,
                style_mode=self.style_mode,
                cancel_check=self.cancel_check,
            )

        return result

    def _validate_and_save_success(
            self,
            images: list[Path],
            result: CaptionWorkflowResult,
            *,
            output_dir: Path,
    ) -> dict:
        check_cancel(self.cancel_check)
        missing_token, short, long_, sample = self.validate(result.captions)

        report_data = build_success_report(
            images=images,
            captions=result.captions,
            caption_model=self.report_model_metadata(),
            caption_status=self.report_status(),
            skipped_annotation=result.skipped_annotation,
            missing_token=missing_token,
            short_captions=short,
            long_captions=long_,
            spot_check_sample=sample,
            enabled=self.enabled,
            mock_runtime=self.mock_runtime,
        )
        check_cancel(self.cancel_check)
        save_success_report(report_data, self.report_path, output_dir)
        return report_data

    # ── Shared helpers ──────────────────────────────────────────────────────────

    def _prepare_output_dir(self) -> Path:
        # Never wipe bbox artifacts here: the ``plk_bbox__*__boxes.json`` reload
        # sidecars store the user's hand-drawn boxes and must survive every re-run
        # (including --force). Captions are regenerated by overwriting their .txt.
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir

    def _collect_source_images(self) -> tuple[list[Path], list[Path]]:
        all_images = img_utils.iter_images(self.dataset_dir)
        images = [p for p in all_images if not _is_bbox_artifact(p)]
        return all_images, images

    def _resolve_pending(
            self,
            images: list[Path],
            output_dir: Path,
    ) -> tuple[dict[Path, Path], list[Path]]:
        """Map each image to its caption ``.txt`` and list which still need one.

        ``pending`` is every image when ``overwrite`` (a --force re-caption);
        otherwise only images whose caption file does not yet exist — the resume set.
        """
        txt_paths = {
            path: (output_dir / path.relative_to(self.dataset_dir)).with_suffix(".txt")
            for path in images
        }
        if self.overwrite:
            pending = list(images)
        else:
            pending = [path for path in images if not txt_paths[path].exists()]
        return txt_paths, pending

    def _log_caption_mode(self, images: list[Path]) -> None:
        if self.style_mode:
            reporter.info(f"Captioning {len(images)} images in style mode (no concept token).")
        else:
            reporter.info(f"Captioning {len(images)} images. Concept token: '{self.concept_token}'")

    def _resolved_report_path(self, output_dir: Path) -> Path:
        return self.report_path or (output_dir / _REPORT_NAME)
