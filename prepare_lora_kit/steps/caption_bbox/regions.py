"""Region caption callback wiring for CaptionBboxStep annotation flows."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


from prepare_lora_kit.cancellation import CancelCheck, check_cancel

from prepare_lora_kit.steps.caption_bbox.artifacts import _save_bbox_training_item


def make_region_captioner(
    *,
    caption_fn: Callable[..., str],
    output_dir: Path,
    captions: dict[str, str],
    concept_token: str | None,
    cancel_check: CancelCheck | None,
) -> Callable[[Any, dict[str, Any] | None], dict[str, str]]:
    """Create the in-UI callback that captions and persists a cropped region.

    ``caption_fn(crop, source_path, box=...)`` produces the raw region caption
    text; the real step routes it through the VLM (captioning the region in the
    context of the full source image when ``box`` is present), the mock returns
    deterministic text. The persistence/normalization around it is identical.
    """

    def _region_captioner(crop: Any, metadata: dict[str, Any] | None = None) -> dict[str, str]:
        check_cancel(cancel_check)
        source_raw = (metadata or {}).get("source_path") or (metadata or {}).get("image_path")
        if not source_raw:
            raise ValueError("Region caption metadata missing source_path")
        source_path = Path(source_raw)
        text = caption_fn(crop, source_path, box=(metadata or {}).get("box"))
        check_cancel(cancel_check)
        result = _save_bbox_training_item(crop, source_path, output_dir, text, concept_token)
        captions[result["crop_path"]] = result["caption"]
        return result

    return _region_captioner
