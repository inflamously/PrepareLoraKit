"""Caption cleaning and consistency utilities."""
from __future__ import annotations
import re

_BOILERPLATE = [
    re.compile(r"^(this image (shows?|depicts?|features?|captures?|presents?)[,:]?\s*)", re.I),
    re.compile(r"^(the (photo|photograph|image|picture) (shows?|depicts?|features?|captures?)[,:]?\s*)", re.I),
    re.compile(r"^(in this (image|photo|photograph|picture)[,:]?\s*)", re.I),
    re.compile(r"^(here (we see|is)[,:]?\s*)", re.I),
    re.compile(r"^(a (photo|photograph|image|picture) (of|showing|depicting|featuring)[,:]?\s*)", re.I),
    re.compile(r"\s*\(?(generated|ai.?generated|stock photo|getty images?|shutterstock)[^.]*\.?\s*$", re.I),
]


def strip_boilerplate(text: str) -> str:
    text = text.strip()
    changed = True
    while changed:
        changed = False
        for pat in _BOILERPLATE:
            new = pat.sub("", text).strip()
            if new != text:
                text = new
                changed = True
    # Capitalise first letter
    if text:
        text = text[0].upper() + text[1:]
    return text


def token_present(caption: str, token: str) -> bool:
    return token.lower() in caption.lower()


def caption_length_ok(caption: str, min_chars: int = 10, max_chars: int = 600) -> bool:
    return min_chars <= len(caption.strip()) <= max_chars


def verify_token_consistency(captions: dict[str, str], token: str) -> list[str]:
    """Return list of paths where token is missing from the caption."""
    return [path for path, cap in captions.items() if not token_present(cap, token)]


_FULL_IMAGE_PROMPT_CONCEPT = """\
You are a LoRA training dataset captioner for modern text-to-image diffusion models.
The user has annotated specific regions of the image:
{bbox_annotations}

Write a single natural-language caption that:
1. Follows this structure where each element is applicable: [image type] [subject] \
[location/environment] [style] [camera/shot details] [lighting] [color palette] [effects/mood]
2. Integrates the annotated regions naturally — do not list them as a bullet list
3. Is 20–80 words (medium length)
4. Places the most important element (subject) before environmental context
5. Uses specific, concrete language — avoid filler words like "detailed", "realistic", "beautiful"
6. Includes the concept token exactly as written: {concept_token}
7. Does NOT start with phrases like "This image shows", "The photo depicts", "Here we see"
8. Outputs ONLY the caption text — nothing else, no commentary, no quotes

Caption:"""

_FULL_IMAGE_PROMPT_STYLE = """\
You are a LoRA training dataset captioner for modern text-to-image diffusion models.
The user has annotated specific regions of the image:
{bbox_annotations}

Write a single natural-language caption that:
1. Describes the visual content richly: subject, location/environment, style, lighting, \
color palette, mood — following this structure where applicable
2. Integrates the annotated regions naturally — do not list them as a bullet list
3. Is 20–80 words (medium length)
4. Places the most important visual element before environmental context
5. Uses specific, concrete language — avoid filler words like "detailed", "realistic", "beautiful"
6. Does NOT include any special trigger word — captions should be pure content descriptions
7. Does NOT start with phrases like "This image shows", "The photo depicts", "Here we see"
8. Outputs ONLY the caption text — nothing else, no commentary, no quotes

Caption:"""


def _format_annotations(bbox_annotations: list[dict]) -> str:
    if bbox_annotations:
        lines = []
        for i, ann in enumerate(bbox_annotations, 1):
            label = ann.get("label", "").strip()
            region = ann.get("region_desc", "")
            if label:
                crop_name = ann.get("crop_name", "")
                crop_note = f", saved crop {crop_name}" if crop_name else ""
                lines.append(f"  Region {i} ({region}{crop_note}): {label}")
        return "\n".join(lines) if lines else "  (no annotations provided)"
    return "  (no annotations — describe the full image)"


def apply_prompt_placeholders(
    template: str,
    annotation_text: str,
    concept_token: str | None,
) -> str:
    """Fill the supported placeholders in a user-authored prompt template.

    Uses plain string replacement (not :meth:`str.format`) so stray ``{`` / ``}``
    characters in a custom prompt never raise. Unknown placeholders are left
    untouched.
    """
    return (
        template
        .replace("{bbox_annotations}", annotation_text)
        .replace("{concept_token}", concept_token or "")
    )


def build_full_image_prompt(
    bbox_annotations: list[dict],
    concept_token: str | None = None,
    *,
    template: str | None = None,
) -> str:
    annotation_text = _format_annotations(bbox_annotations)

    if template:
        return apply_prompt_placeholders(template, annotation_text, concept_token)

    if concept_token:
        return _FULL_IMAGE_PROMPT_CONCEPT.format(
            bbox_annotations=annotation_text,
            concept_token=concept_token,
        )
    return _FULL_IMAGE_PROMPT_STYLE.format(bbox_annotations=annotation_text)
