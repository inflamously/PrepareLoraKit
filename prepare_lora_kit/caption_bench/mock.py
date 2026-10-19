"""GPU-free stand-in for ``vlm.CaptionRuntime`` (``plk caption-bench run --mock``)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from prepare_lora_kit.pipeline.configs import CaptionBboxConfig


class MockBenchRuntime:
    """Deterministic captions that echo their inputs, so the bench flow is testable."""

    def __init__(self, config: CaptionBboxConfig) -> None:
        self.config = config
        self.pass_counts: dict[str, int] = {}
        self.unloaded = False

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "model_id": self.config.caption_model_id or "mock",
            "caption_strategy": self.config.caption_strategy,
            "mock": True,
            "passes": dict(self.pass_counts),
        }

    def caption_image(
            self,
            image_path: Path,
            annotations: list[dict],
            concept_token: str | None,
            *,
            max_new_tokens: int = 200,
            trace: dict[str, Any] | None = None,
    ) -> str:
        labels = ", ".join(a["label"] for a in annotations if a.get("label"))
        caption = f"a {self.config.caption_strategy} mock caption of {Path(image_path).stem}"
        if labels:
            caption = f"{caption} with {labels}"
        self.pass_counts["compose"] = self.pass_counts.get("compose", 0) + 1
        if trace is not None:
            trace["draft"] = caption
        return caption

    def unload(self) -> None:
        self.unloaded = True
