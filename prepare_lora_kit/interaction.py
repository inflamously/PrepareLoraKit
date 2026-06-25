"""Human-in-the-loop interaction hooks used by pipeline steps.

The CLI implementation keeps the existing tkinter/easygui behavior. Other
frontends can provide the same methods to collect decisions without importing
desktop UI code from the step modules.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Protocol

RegionCaptioner = Callable[[object, dict[str, Any] | None], dict[str, Any] | str]


class InteractionProvider(Protocol):
    """Protocol for review and annotation interactions."""

    def source_review(self, scored: list[tuple[Path, dict]]) -> dict[str, str]:
        """Return per-image quality decisions: keep, reject, or flag."""

    def annotate_image(
            self,
            path: Path,
            *,
            captioner: RegionCaptioner | None = None,
    ) -> tuple[list[dict], bool, bool]:
        """Return annotations, skipped flag, and skip-all flag for one image."""

    def vae_review(self, items: list[dict]) -> dict[str, str]:
        """Return per-original VAE gate decisions: keep, drop, or replace."""


class CliInteractionProvider:
    """Default provider preserving the existing CLI UI/fallback behavior."""

    def source_review(self, scored: list[tuple[Path, dict]]) -> dict[str, str]:
        from .steps.s1_source.review import _review_gallery_or_fallback

        return _review_gallery_or_fallback(scored)

    def annotate_image(
            self,
            path: Path,
            *,
            captioner: RegionCaptioner | None = None,
    ) -> tuple[list[dict], bool, bool]:
        # Region annotation is a UI-only feature; the CLI captions full images.
        return [], True, False

    def vae_review(self, items: list[dict]) -> dict[str, str]:
        from .steps.s4_vae_gate.review import _review_artifact_decisions

        return _review_artifact_decisions(items)


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
