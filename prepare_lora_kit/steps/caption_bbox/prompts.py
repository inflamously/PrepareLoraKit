"""Caption prompt templates, prompt assembly, and caption text-QA helpers.

Single source of truth for the built-in full-image / region prompts (shared by the
VLM runtime and the UI's virtual "Default" prompt-library entry) plus the small text
utilities used to clean and validate generated captions. Lives beside the caption
step because every consumer is caption-specific.
"""
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

Describe ONLY what is clearly and directly visible. Do not invent, guess, or add people, \
faces, objects, backgrounds, or settings that are not actually present. If the image is a \
single object on a plain or empty background, describe just that object and its background — \
do not imagine a scene, a person, or a story.

Write a single natural-language caption that:
1. Leads with the main visible subject, then adds only real context, in roughly this order \
when applicable: [image type] [main subject] [setting — only if a real setting is visible] \
[style] [lighting] [color palette] [mood]. Omit any element that is not present; a plain \
background is not a "setting".
2. Integrates the annotated regions naturally — do not list them as bullet points
3. Is 20–80 words; shorter is fine for a simple single object
4. Uses specific, concrete language — avoid filler like "detailed", "realistic", "beautiful"
5. Includes the concept token exactly as written: {concept_token}
6. Does NOT start with phrases like "This image shows", "The photo depicts", "Here we see"
7. Outputs ONLY the caption text — nothing else, no commentary, no quotes

Caption:"""

_FULL_IMAGE_PROMPT_STYLE = """\
You are a LoRA training dataset captioner for modern text-to-image diffusion models.
The user has annotated specific regions of the image:
{bbox_annotations}

Describe ONLY what is clearly and directly visible. Do not invent, guess, or add people, \
faces, objects, backgrounds, or settings that are not actually present. If the image is a \
single object on a plain or empty background, describe just that object and its background — \
do not imagine a scene, a person, or a story.

Write a single natural-language caption that:
1. Leads with the main visible subject, then adds only real context, in roughly this order \
when applicable: [image type] [main subject] [setting — only if a real setting is visible] \
[style] [lighting] [color palette] [mood]. Omit any element that is not present; a plain \
background is not a "setting".
2. Integrates the annotated regions naturally — do not list them as bullet points
3. Is 20–80 words; shorter is fine for a simple single object
4. Uses specific, concrete language — avoid filler like "detailed", "realistic", "beautiful"
5. Does NOT include any special trigger word — captions should be pure content descriptions
6. Does NOT start with phrases like "This image shows", "The photo depicts", "Here we see"
7. Outputs ONLY the caption text — nothing else, no commentary, no quotes

Caption:"""


# Region-crop caption instruction. Lives here (not in vlm.py) so the runtime default and
# the UI "Default" prompt-library entry share a single source of truth.
_REGION_PROMPT = (
    "Describe what is actually visible in this crop with a short, literal phrase: a few "
    "comma-separated words or descriptors. Name only what you can clearly see — do not "
    "guess or invent. Do not mention that this is a crop or region. Output only the description."
)


# Natural-language placement for a localized box, keyed by (vertical, horizontal) zone.
_PLACEMENT_PROSE = {
    ("top", "left"): "in the upper-left", ("top", "center"): "at the top-center", ("top", "right"): "in the upper-right",
    ("middle", "left"): "on the left", ("middle", "center"): "in the center", ("middle", "right"): "on the right",
    ("bottom", "left"): "in the lower-left", ("bottom", "center"): "at the bottom-center", ("bottom", "right"): "in the lower-right",
}


def describe_box_position(x1: float, y1: float, x2: float, y2: float) -> str:
    """Turn a normalized [0,1] bounding box into a natural spatial phrase.

    VL models (and the downstream text encoder) read everyday spatial English far
    better than coordinate floats or synthetic grid jargon, so the box is measured
    precisely but rendered as plain prose, e.g. ``"in the upper-left"``,
    ``"across the bottom"``, ``"down the right side"``. Small regions — the ones a
    captioner is most likely to drop — are flagged as ``"a small element ..."`` to
    steer the model into mentioning them.
    """
    x1, x2 = sorted((max(0.0, min(1.0, x1)), max(0.0, min(1.0, x2))))
    y1, y2 = sorted((max(0.0, min(1.0, y1)), max(0.0, min(1.0, y2))))
    w, h = x2 - x1, y2 - y1
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

    wide, tall = w >= 0.66, h >= 0.66
    if wide and tall:
        return "filling the frame" if w * h >= 0.75 else "spread across most of the frame"

    vz = "top" if cy < 0.30 else ("middle" if cy < 0.62 else "bottom")
    hz = "left" if cx < 0.30 else ("center" if cx < 0.62 else "right")

    if wide:
        return {"top": "across the top", "middle": "across the middle", "bottom": "across the bottom"}[vz]
    if tall:
        return {"left": "down the left side", "center": "down the center", "right": "down the right side"}[hz]

    placement = _PLACEMENT_PROSE[(vz, hz)]
    if w * h < 0.06:
        return f"a small element {placement}"
    return placement


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


def default_prompt_text(kind: str) -> str:
    """Return the canonical built-in prompt text for a prompt-library ``kind``.

    Single source of truth for the "Default" entries surfaced by the UI prompt
    library (:mod:`..caption_prompts.prompt_registry`): the runtime fallback
    constants below and the UI's Default are guaranteed identical because both
    read from here. ``full_image`` returns the concept-token variant (what the
    library previously shipped as its Default).
    """
    if kind == "full_image":
        return _FULL_IMAGE_PROMPT_CONCEPT
    if kind == "region":
        return _REGION_PROMPT
    raise ValueError(f"Unknown default prompt kind '{kind}'. Expected 'full_image' or 'region'.")


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


# ── Grounded 3-pass prompts (observe → compose → verify) ────────────────────────
#
# The single-shot full-image prompt asks the model to observe, compose, style,
# integrate regions, inject the token and avoid hallucination all at once, which
# yields generic or tag-like captions. These three prompts split that work into
# grounded passes over the *same* loaded VLM (see ``grounded.py``). All three fill
# their placeholders with plain ``str.replace`` (not ``.format``) because ``facts``
# and ``draft`` are model-generated and may contain stray ``{``/``}``.

_OBSERVE_PROMPT = """\
You are analysing an image to build an accurate training caption. First, OBSERVE it.
{bbox_annotations}

List ONLY what is clearly and directly visible. Never guess, infer, or invent people, \
faces, objects, or settings that are not actually present. Write "not visible" for any \
heading that does not apply. Be concise and concrete — a few words per line.

SUBJECT:
COUNT:
APPEARANCE / CLOTHING:
POSE / ACTION:
SETTING / BACKGROUND:
NOTABLE OBJECTS:
FRAMING / SHOT:
LIGHTING:
COLOR PALETTE:
MEDIUM / STYLE:

Account for any annotated regions listed above. Output only the filled-in list."""


_COMPOSE_PROMPT_CONCEPT = """\
You are writing a single LoRA training caption for a text-to-image diffusion model.
Use ONLY these observed facts — do not add anything not listed, and drop anything marked \
"not visible":
{facts}

Annotated regions to weave in naturally:
{bbox_annotations}

Write ONE natural-language caption that:
1. Leads with the main subject, then real context in roughly this order when present: \
[image type] [main subject] [setting] [style] [lighting] [color palette] [mood]. A plain \
background is not a "setting".
2. Integrates the annotated regions naturally — not as a list.
3. Is 20–80 words; shorter is fine for a simple single object.
4. Uses specific, concrete language — avoid filler like "detailed", "realistic", "beautiful".
5. Includes the concept token exactly as written: {concept_token}
6. Does NOT start with "This image shows", "The photo depicts", "Here we see".
7. Outputs ONLY the caption text — nothing else, no commentary, no quotes.

Caption:"""


_COMPOSE_PROMPT_STYLE = """\
You are writing a single LoRA training caption for a text-to-image diffusion model.
Use ONLY these observed facts — do not add anything not listed, and drop anything marked \
"not visible":
{facts}

Annotated regions to weave in naturally:
{bbox_annotations}

Write ONE natural-language caption that:
1. Leads with the main subject, then real context in roughly this order when present: \
[image type] [main subject] [setting] [style] [lighting] [color palette] [mood]. A plain \
background is not a "setting".
2. Integrates the annotated regions naturally — not as a list.
3. Is 20–80 words; shorter is fine for a simple single object.
4. Uses specific, concrete language — avoid filler like "detailed", "realistic", "beautiful".
5. Does NOT include any special trigger word — captions should be pure content descriptions.
6. Does NOT start with "This image shows", "The photo depicts", "Here we see".
7. Outputs ONLY the caption text — nothing else, no commentary, no quotes.

Caption:"""


_VERIFY_PROMPT_CONCEPT = """\
Here is a draft caption for the image:
{draft}

Compare it against the image and correct it:
- Remove any detail that is NOT actually visible (hallucinations).
- Add the single most important visible element if it is missing.
- Keep it faithful and fluent, in the same style and attribute order.
- Keep the concept token exactly as written: {concept_token}
- Do NOT start with "This image shows", "The photo depicts", "Here we see".

Output ONLY the corrected caption text — nothing else, no commentary, no quotes."""


_VERIFY_PROMPT_STYLE = """\
Here is a draft caption for the image:
{draft}

Compare it against the image and correct it:
- Remove any detail that is NOT actually visible (hallucinations).
- Add the single most important visible element if it is missing.
- Keep it faithful and fluent, in the same style and attribute order.
- Do NOT add any special trigger word — keep it a pure content description.
- Do NOT start with "This image shows", "The photo depicts", "Here we see".

Output ONLY the corrected caption text — nothing else, no commentary, no quotes."""


def build_observe_prompt(bbox_annotations: list[dict]) -> str:
    """Stage A: instruct the VLM to list only-visible facts under fixed headings."""
    annotation_text = _format_annotations(bbox_annotations)
    return _OBSERVE_PROMPT.replace("{bbox_annotations}", annotation_text)


def build_compose_prompt(
    facts: str,
    bbox_annotations: list[dict],
    concept_token: str | None,
    *,
    style_mode: bool,
    template: str | None = None,
) -> str:
    """Stage B: turn observed ``facts`` + regions into one fluent caption.

    A custom ``template`` (the user's ``caption_prompt``) overrides the built-in
    compose instruction; the observed facts are prepended as grounding context so the
    prompt library keeps working while still benefiting from the observe pass.
    """
    annotation_text = _format_annotations(bbox_annotations)
    if template:
        instruction = apply_prompt_placeholders(template, annotation_text, concept_token)
        return f"Observed facts about the image (use only these):\n{facts}\n\n{instruction}"

    base = _COMPOSE_PROMPT_STYLE if style_mode else _COMPOSE_PROMPT_CONCEPT
    return (
        base
        .replace("{facts}", facts)
        .replace("{bbox_annotations}", annotation_text)
        .replace("{concept_token}", concept_token or "")
    )


def build_verify_prompt(
    draft: str,
    concept_token: str | None,
    *,
    style_mode: bool,
) -> str:
    """Stage C: instruct the VLM to remove non-visible claims and fill omissions."""
    base = _VERIFY_PROMPT_STYLE if style_mode else _VERIFY_PROMPT_CONCEPT
    return (
        base
        .replace("{draft}", draft)
        .replace("{concept_token}", concept_token or "")
    )
