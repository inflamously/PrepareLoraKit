"""Human-in-the-loop hooks, so a frontend can supply decisions without step modules
importing UI code.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

RegionCaptioner = Callable[[object, dict[str, Any] | None], dict[str, Any] | str]


class InteractionProvider(Protocol):
    """The single-image hook ``annotate_dataset_via_images`` drives.

    Only ``annotate_image`` is required. The review hooks (``source_review``,
    ``vae_review``, ``caption_verify``) are optional and probed with ``getattr``,
    so a frontend that cannot present a given gallery simply omits them.
    """

    def annotate_image(
            self,
            path: Path,
            *,
            captioner: RegionCaptioner | None = None,
    ) -> tuple[list[dict], bool, bool]:
        ...


def annotate_dataset_via_images(
        provider: InteractionProvider,
        images: list[dict],
        *,
        captioner: RegionCaptioner | None = None,
) -> tuple[dict[str, dict], bool]:
    """Batch-annotate by looping a provider's per-image ``annotate_image``.

    The default path for providers (CLI, tests) that only implement the
    single-image hook. A per-image ``skipped`` from ``annotate_image`` historically
    meant "no regions, but still caption the full image", so every image maps to
    ``skipped=False`` here; ``skip_all`` just stops prompting for the rest (they are
    still captioned with no regions, preserving the prior CLI behavior).
    """
    decisions: dict[str, dict] = {}
    skip_all = False
    for descriptor in images:
        path = Path(descriptor["path"])
        if skip_all:
            annotations: list[dict] = []
        else:
            annotations, _skipped, skip_all = provider.annotate_image(
                path, captioner=captioner,
            )
        decisions[str(path)] = {"annotations": annotations, "skipped": False}
    return decisions, False


class CliInteractionProvider:
    """Default provider preserving the existing CLI UI/fallback behavior."""

    def source_review(self, scored: list[tuple[Path, dict]]) -> dict[str, str]:

        from prepare_lora_kit.steps.quality_gate.review import _review_gallery_or_fallback
        return _review_gallery_or_fallback(scored)

    def annotate_image(
            self,
            path: Path,
            *,
            captioner: RegionCaptioner | None = None,
    ) -> tuple[list[dict], bool, bool]:
        # Region annotation is a UI-only feature; the CLI captions full images.
        return [], True, False

    # Deliberately no ``caption_verify``: it needs a side-by-side gallery with
    # an editable caption per image, so it is UI-only. CaptionVerifierStep
    # probes with ``getattr`` and reports a clean skip-with-reason for headless
    # runs, which is more informative than an empty no-op review.

    def vae_review(self, items: list[dict]) -> dict[str, str]:

        from prepare_lora_kit.steps.vae_gate.review import _review_artifact_decisions
        return _review_artifact_decisions(items)

    def upscale_review(self, items: list[dict]) -> dict[str, str]:

        from prepare_lora_kit.steps.upscale.review import _review_flagged_decisions
        return _review_flagged_decisions(items)

    def export_review(self, payload: dict[str, Any]) -> dict[str, Any]:

        from prepare_lora_kit.steps.export_step.review import review_export_cli
        return review_export_cli(payload)


class CliBboxRegionProvider(CliInteractionProvider):
    """CLI provider that replays pre-specified bbox regions for one image.

    Region annotations enrich only the full-image caption prompt (region-context
    only); no per-region crop/training artifacts are produced, so the captioner
    callback is never invoked. Other images in the dataset caption normally.
    """

    def __init__(self, target_image: Path, boxes: list[dict]):
        # boxes: list of {"x1","y1","x2","y2","label"} with floats normalized to [0,1].
        self._target = Path(target_image).resolve()
        self._boxes = boxes

    def annotate_image(
            self,
            path: Path,
            *,
            captioner: RegionCaptioner | None = None,
    ) -> tuple[list[dict], bool, bool]:
        if Path(path).resolve() != self._target or not self._boxes:
            return [], True, False
        annotations = [dict(box) for box in self._boxes]
        return annotations, False, False
