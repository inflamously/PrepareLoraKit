from pathlib import Path
from typing import Protocol, Any

from prepare_lora_kit.interaction import RegionCaptioner


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

    def annotate_dataset(
            self,
            images: list[dict],
            *,
            captioner: RegionCaptioner | None = None,
    ) -> tuple[dict[str, dict], bool]:
        """Annotate a whole batch in one interaction.

        ``images`` is a list of descriptors ``{"path", "name", "annotations"
        (reloaded boxes), "done"}``. Returns ``(decisions, skip_all)`` where
        ``decisions[str(path)] = {"annotations": [...], "skipped": bool}``;
        ``skipped`` means "do not caption this image" (keep any existing caption).
        """

    def vae_review(self, items: list[dict]) -> dict[str, str]:
        """Return per-original VAE gate decisions: keep, drop, or replace."""

    def upscale_review(self, items: list[dict]) -> dict[str, str]:
        """Return per-original Step 3 decisions for flagged images: upscale or skip."""

    def export_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Preview the ExportStep diff and return ``{confirmed, excluded}``.

        ``payload`` holds the categorized diff (``added``/``modified``/
        ``orphaned`` plus ``counts`` and ``target_dir``). ``excluded`` lists the
        target-relative paths the user chose not to write.
        """
