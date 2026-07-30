from pathlib import Path
from typing import Any, Protocol

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

    def caption_verify(
            self,
            items: list[dict],
            *,
            generator: Any | None = None,
            preview_dir: Path | None = None,
            settings: dict[str, Any] | None = None,
    ) -> dict[str, dict]:
        """Review captions against text-to-image renders of themselves.

        ``items`` are descriptors ``{"path", "name", "caption", "caption_path"}``.
        ``generator`` is a ``(prompt, options) -> dict`` callable the provider
        may invoke *while the review is open* — the UI calls it from its own RPC
        thread each time the user asks for a render.

        Returns ``{str(path): {"verdict", "caption"}}`` where ``verdict`` is one
        of ``correct``/``generic``/``wrong`` and ``caption`` is the (possibly
        edited) text to write back to ``<stem>.txt``.
        """

    def vae_review(self, items: list[dict]) -> dict[str, str]:
        """Return per-original VAE gate decisions: keep or drop."""

    def upscale_review(self, items: list[dict]) -> dict[str, str]:
        """Return per-original Step 3 decisions for flagged images: upscale or skip."""

    def bucket_pool_details(self, report: dict[str, Any], report_path: Path) -> bool:
        """Show read-only bucket assignments and wait for confirmation."""

    def export_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Preview the ExportStep diff and return ``{confirmed, excluded}``.

        ``payload`` holds the categorized diff (``added``/``modified``/
        ``orphaned`` plus ``counts`` and ``target_dir``). ``excluded`` lists the
        target-relative paths the user chose not to write.
        """
