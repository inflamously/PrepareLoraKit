"""CaptionBboxStep ``--bbox`` region-context use-case for the ``step`` command.

Parses ``--bbox`` region specs, resolves which dataset image they apply to, and
builds the :class:`CliBboxRegionProvider` interaction that feeds those regions
into CaptionBboxStep's annotate substep.
"""
from __future__ import annotations
from pathlib import Path

import click


def _parse_bbox(raw: str, width: int, height: int) -> dict:
    """Parse a ``X1,Y1,X2,Y2[:LABEL]`` region spec into a normalized annotation.

    Coordinates are pixels by default; if all four values are <= 1.0 they are
    treated as already-normalized [0,1]. Out-of-order coords are sorted and
    out-of-bounds values clamped. The optional label is split on the first ':'.
    """
    coords_part, _, label = raw.partition(":")
    parts = [p.strip() for p in coords_part.split(",")]
    if len(parts) != 4:
        raise click.BadParameter(
            f"--bbox must be 'X1,Y1,X2,Y2[:LABEL]', got '{raw}'", param_hint="--bbox")
    try:
        x1, y1, x2, y2 = (float(p) for p in parts)
    except ValueError:
        raise click.BadParameter(
            f"--bbox coordinates must be numeric, got '{raw}'", param_hint="--bbox")

    if not all(v <= 1.0 for v in (x1, y1, x2, y2)):
        x1, x2 = x1 / width, x2 / width
        y1, y2 = y1 / height, y2 / height

    x1, x2 = sorted((x1, x2))
    y1, y2 = sorted((y1, y2))

    def _clamp(v: float) -> float:
        return max(0.0, min(1.0, v))

    return {
        "x1": _clamp(x1), "y1": _clamp(y1),
        "x2": _clamp(x2), "y2": _clamp(y2),
        "label": label.strip(),
    }


def _resolve_bbox_target(working_dir: Path, bbox_image: str | None) -> Path:
    """Resolve which dataset image the --bbox regions apply to."""

    from prepare_lora_kit.utils import image as img_utils
    if bbox_image:
        target = working_dir / bbox_image
        if not target.exists():
            raise click.BadParameter(
                f"--bbox-image '{bbox_image}' not found in working dataset {working_dir}",
                param_hint="--bbox-image")
        return target

    images = img_utils.iter_images(working_dir)
    if not images:
        raise click.ClickException(f"No images in working dataset {working_dir}.")
    if len(images) > 1:
        raise click.BadParameter(
            "Dataset has multiple images; use --bbox-image to choose which one "
            "the --bbox regions apply to.", param_hint="--bbox-image")
    return images[0]


def build_bbox_interaction(working_dir: Path, bboxes, bbox_image: str | None):
    """Build the region-context interaction for the given ``--bbox`` specs.

    Returns ``(interaction, target, boxes)`` where ``interaction`` is a
    :class:`CliBboxRegionProvider` carrying the parsed ``boxes`` for ``target``,
    the resolved dataset image the regions apply to.
    """
    from PIL import Image


    from prepare_lora_kit.interaction import CliBboxRegionProvider
    target = _resolve_bbox_target(working_dir, bbox_image)
    with Image.open(target) as im:
        width, height = im.size
    boxes = [_parse_bbox(raw, width, height) for raw in bboxes]
    return CliBboxRegionProvider(target, boxes), target, boxes
