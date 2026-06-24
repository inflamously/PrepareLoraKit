"""Region caption callback wiring for Step 5 annotation flows."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ...cancellation import CancelCheck, check_cancel

from .artifacts import _save_bbox_training_item


def make_region_captioner(
    *,
    runtime: Any,
    output_dir: Path,
    captions: dict[str, str],
    concept_token: str | None,
    cancel_check: CancelCheck | None,
) -> Callable[[Any, dict[str, Any] | None], dict[str, str]]:
    """Create the in-UI callback that captions and persists a cropped region."""

    def _region_captioner(crop: Any, metadata: dict[str, Any] | None = None) -> dict[str, str]:
        check_cancel(cancel_check)
        source_raw = (metadata or {}).get("source_path") or (metadata or {}).get("image_path")
        if not source_raw:
            raise ValueError("Region caption metadata missing source_path")
        source_path = Path(source_raw)
        text = runtime.caption_region(crop)
        check_cancel(cancel_check)
        result = _save_bbox_training_item(crop, source_path, output_dir, text, concept_token)
        captions[result["crop_path"]] = result["caption"]
        return result

    return _region_captioner
