"""Single source of truth for the built-in full-image and region caption prompts."""
from __future__ import annotations

_FULL_IMAGE_PROMPT_CONCEPT = """\
You are a LoRA training dataset captioner for modern text-to-image diffusion models.
The user has annotated specific regions of the image. Those labels are ground truth — keep \
their wording, and never rename or contradict them:
{bbox_annotations}

Describe ONLY what is clearly and directly visible. Do not invent, guess, or add people, \
faces, objects, backgrounds, or settings that are not actually present. If the image is a \
single object on a plain or empty background, describe just that object and its background — \
do not imagine a scene, a person, or a story. If something is present that you cannot \
confidently name, describe what it looks like — shape, material, colour, parts — instead of \
guessing a name for it.

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
The user has annotated specific regions of the image. Those labels are ground truth — keep \
their wording, and never rename or contradict them:
{bbox_annotations}

Describe ONLY what is clearly and directly visible. Do not invent, guess, or add people, \
faces, objects, backgrounds, or settings that are not actually present. If the image is a \
single object on a plain or empty background, describe just that object and its background — \
do not imagine a scene, a person, or a story. If something is present that you cannot \
confidently name, describe what it looks like — shape, material, colour, parts — instead of \
guessing a name for it.

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


# Region caption instructions. Live here (not in vlm.py) so the runtime defaults and
# the UI "Default" prompt-library entry share a single source of truth.
#
# Bare-crop fallback: a natural phrase, not comma-separated tags (the old tag-style
# wording produced inaccurate tag lists). Used when no source image/box is available
# or the model cannot follow prompts.
_REGION_PROMPT = (
    "Describe what is shown here in ONE short, natural phrase — not a list of tags. "
    "Name the main object or subject and its most important visible attributes "
    "(material, colour, shape, notable detail). Only describe what is clearly visible; "
    "do not guess. If you cannot confidently name it, describe its appearance instead of "
    "guessing a name. Do not mention that this is a crop or region. Output only the phrase."
)

# Region caption with a known origin: the model still sees ONLY the crop (a region
# caption must describe the box contents, never the surrounding scene), but is told
# where the crop sits in the source image as a hint for partial/ambiguous objects.
_REGION_WITH_POSITION_PROMPT = (
    "This is a cropped detail taken from {region_position} of a larger image. "
    "Describe ONLY what is inside this crop in ONE short, natural phrase — not a list "
    "of tags and not a full-scene sentence. Name the main object or subject and its "
    "most important visible attributes (material, colour, shape, notable detail). "
    "Only describe what is clearly visible; do not guess and do not describe the "
    "larger image. If you cannot confidently name it, describe its appearance instead "
    "of guessing a name. Output only the phrase."
)


def build_region_prompt(
    position: str | None = None,
    *,
    template: str | None = None,
    domain_brief: str | None = None,
) -> str:
    """Return the region caption instruction (always applied to the crop).

    ``position`` is the :func:`describe_box_position` prose for where the crop sits
    in the source image; when given, it is included as an origin hint. A custom
    ``template`` (the project's ``region_prompt``) overrides the built-ins and may
    use the ``{region_position}`` placeholder (empty when the origin is unknown).
    """
    if template:
        prompt = (
            apply_prompt_placeholders(template, "", None)
            .replace("{region_position}", position or "")
        )
    elif position:
        prompt = _REGION_WITH_POSITION_PROMPT.replace("{region_position}", position)
    else:
        prompt = _REGION_PROMPT
    return apply_domain_brief(prompt, domain_brief)


# Natural-language placement for a localized box, keyed by (vertical, horizontal) zone.
_PLACEMENT_PROSE = {
    ("top", "left"): "in the upper-left",
    ("top", "center"): "at the top-center",
    ("top", "right"): "in the upper-right",
    ("middle", "left"): "on the left",
    ("middle", "center"): "in the center",
    ("middle", "right"): "on the right",
    ("bottom", "left"): "in the lower-left",
    ("bottom", "center"): "at the bottom-center",
    ("bottom", "right"): "in the lower-right",
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
        return {"top": "across the top", "middle": "across the middle",
                "bottom": "across the bottom"}[vz]
    if tall:
        return {"left": "down the left side", "center": "down the center",
                "right": "down the right side"}[hz]

    placement = _PLACEMENT_PROSE[(vz, hz)]
    if w * h < 0.06:
        return f"a small element {placement}"
    return placement


def _annotation_lines(bbox_annotations: list[dict]) -> list[str]:
    """One ``Region N (where): label`` line per *labelled* annotation."""
    lines = []
    for i, ann in enumerate(bbox_annotations or (), 1):
        label = ann.get("label", "").strip()
        region = ann.get("region_desc", "")
        if label:
            crop_name = ann.get("crop_name", "")
            crop_note = f", saved crop {crop_name}" if crop_name else ""
            lines.append(f"  Region {i} ({region}{crop_note}): {label}")
    return lines


def _format_annotations(bbox_annotations: list[dict]) -> str:
    lines = _annotation_lines(bbox_annotations)
    if lines:
        return "\n".join(lines)
    if bbox_annotations:
        return "  (no annotations provided)"
    return "  (no annotations — describe the full image)"


# A VLM facing an unfamiliar domain cannot abstain its way to a *right* answer — it can
# only avoid a wrong one. The domain brief is the one lever that supplies the missing
# knowledge, so it is prepended to every prompt that names or describes anything, ahead
# of the model's own priors. Deliberately not a template placeholder: it must reach
# user-authored prompts from the library too, without them having to opt in.
_DOMAIN_SECTION = """\
Domain context for this dataset — authoritative, and it outranks your own assumptions \
about what things are:
{domain_brief}

"""


def apply_domain_brief(prompt: str, domain_brief: str | None) -> str:
    """Prepend the project's domain brief to ``prompt`` when one is set."""
    brief = (domain_brief or "").strip()
    if not brief:
        return prompt
    return _DOMAIN_SECTION.replace("{domain_brief}", brief) + prompt


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
    domain_brief: str | None = None,
) -> str:
    annotation_text = _format_annotations(bbox_annotations)

    if template:
        prompt = apply_prompt_placeholders(template, annotation_text, concept_token)
    elif concept_token:
        prompt = _FULL_IMAGE_PROMPT_CONCEPT.format(
            bbox_annotations=annotation_text,
            concept_token=concept_token,
        )
    else:
        prompt = _FULL_IMAGE_PROMPT_STYLE.format(bbox_annotations=annotation_text)
    return apply_domain_brief(prompt, domain_brief)


# ── Grounded prompts (observe → compose → gap-fill) ─────────────────────────────
#
# The single-shot full-image prompt asks the model to observe, compose, style,
# integrate regions, inject the token and avoid hallucination all at once, which
# yields generic or tag-like captions. These prompts split that work into grounded
# passes over the *same* loaded VLM (see ``grounded.py``). The last one asks for a
# list of omissions rather than a corrected caption, so the pass cannot overwrite
# the draft — see ``gap_fill.py`` for why that had to be a format change and not a
# wording change. All fill their placeholders with plain ``str.replace`` (not
# ``.format``) because ``facts`` and ``draft`` are model-generated and may contain
# stray ``{``/``}``.

_OBSERVE_PROMPT = """\
You are analysing an image to build an accurate training caption. First, OBSERVE it.
{bbox_annotations}

List ONLY what is clearly and directly visible. Never guess, infer, or invent people, \
faces, objects, or settings that are not actually present. Write "not visible" for any \
heading that does not apply. Be concise and concrete — a few words per line.

If something IS present but you cannot confidently name it, do NOT substitute a familiar \
name for it. Describe what it actually looks like — shape, material, colour, parts — and \
begin that line with "?". An accurate description is worth more than a confident wrong name.

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
{facts_section}
{annotations_section}
Write ONE natural-language caption that:
1. Leads with the main subject, then real context in roughly this order when present: \
[image type] [main subject] [setting] [style] [lighting] [color palette] [mood]. A plain \
background is not a "setting".
2. Integrates any annotated regions naturally — not as a list.
3. Is 20–80 words; shorter is fine for a simple single object.
4. Uses specific, concrete language — avoid filler like "detailed", "realistic", "beautiful".
5. Includes the concept token exactly as written: {concept_token}
6. Does NOT start with "This image shows", "The photo depicts", "Here we see".
7. Outputs ONLY the caption text — nothing else, no commentary, no quotes.

Caption:"""


_COMPOSE_PROMPT_STYLE = """\
You are writing a single LoRA training caption for a text-to-image diffusion model.
{facts_section}
{annotations_section}
Write ONE natural-language caption that:
1. Leads with the main subject, then real context in roughly this order when present: \
[image type] [main subject] [setting] [style] [lighting] [color palette] [mood]. A plain \
background is not a "setting".
2. Integrates any annotated regions naturally — not as a list.
3. Is 20–80 words; shorter is fine for a simple single object.
4. Uses specific, concrete language — avoid filler like "detailed", "realistic", "beautiful".
5. Does NOT include any special trigger word — captions should be pure content descriptions.
6. Does NOT start with "This image shows", "The photo depicts", "Here we see".
7. Outputs ONLY the caption text — nothing else, no commentary, no quotes.

Caption:"""


_GAP_PROMPT = """\
Look at the image, then read this caption of it:
{draft}

List anything clearly visible in the image that the caption fails to mention.

- One short noun phrase per line, at most 3 lines.
- Only concrete visible things: subjects, objects, setting, notable colour or lighting.
- Do NOT repeat anything the caption already covers, even in different words.
- Do NOT rewrite the caption, do NOT explain, do NOT number or bullet the lines.
- If the caption is already complete, output exactly: NONE"""


def build_observe_prompt(
    bbox_annotations: list[dict],
    *,
    domain_brief: str | None = None,
) -> str:
    """Stage A: instruct the VLM to list only-visible facts under fixed headings."""
    annotation_text = _format_annotations(bbox_annotations)
    return apply_domain_brief(
        _OBSERVE_PROMPT.replace("{bbox_annotations}", annotation_text), domain_brief
    )


# Where COMPOSE's grounding comes from. An empty ``facts`` string means the observe
# pass was skipped because the human's region labels already ground the image (see
# ``grounded._annotations_suffice``) — the caption must then read the global attributes
# labels cannot supply off the image, which COMPOSE can do because it is
# image-conditioned too.
_FACTS_SECTION_OBSERVED = """\
Use ONLY these observed facts — do not add anything not listed, and drop anything marked \
"not visible":
{facts}
"""

# Appended only when the observe pass actually abstained on something, so the prompt
# stays tight in the common case.
_UNNAMED_FACTS_NOTE = """\
A fact beginning with "?" is something the observer could not confidently name: keep its \
description of appearance, never invent a name for it, and do not repeat the "?" marker.
"""

_FACTS_SECTION_ANNOTATED = """\
No separate observation pass was run. Read every attribute the annotated regions below do \
not cover — setting, framing, lighting, colour palette, medium and style — directly from \
the image, and describe only what is clearly visible there.
"""

# Region labels are human-authored, so COMPOSE is told they outrank its own reading of
# the image. Enforced afterwards too: ``validation.enforce_region_labels`` re-inserts a
# label the model dropped anyway.
_ANNOTATIONS_SECTION = """\
Annotated regions — labelled by a human, so they are ground truth. Weave them into the \
caption naturally, keeping each label's wording, and never rename or contradict them:
{bbox_annotations}
"""

_NO_ANNOTATIONS_SECTION = "No regions were annotated — describe the full image.\n"


def _facts_section(facts: str) -> str:
    if facts and facts.strip():
        facts = facts.strip()
        section = _FACTS_SECTION_OBSERVED.replace("{facts}", facts)
        return f"{section}\n{_UNNAMED_FACTS_NOTE}" if "?" in facts else section
    return _FACTS_SECTION_ANNOTATED


def _annotations_section(bbox_annotations: list[dict]) -> str:
    lines = _annotation_lines(bbox_annotations)
    if not lines:
        return _NO_ANNOTATIONS_SECTION
    return _ANNOTATIONS_SECTION.replace("{bbox_annotations}", "\n".join(lines))


def build_compose_prompt(
    facts: str,
    bbox_annotations: list[dict],
    concept_token: str | None,
    *,
    style_mode: bool,
    template: str | None = None,
    domain_brief: str | None = None,
) -> str:
    """Stage B: turn observed ``facts`` + regions into one fluent caption.

    An empty ``facts`` switches the grounding section to the annotation-led variant
    rather than emitting an empty fact list — the absence of facts *is* the signal
    that the observe pass was skipped, so the two can never drift out of sync.

    A custom ``template`` (the user's ``caption_prompt``) overrides the built-in
    compose instruction; observed facts, when there are any, are prepended as
    grounding context so the prompt library keeps working.
    """
    annotation_text = _format_annotations(bbox_annotations)
    if template:
        instruction = apply_prompt_placeholders(template, annotation_text, concept_token)
        if facts and facts.strip():
            instruction = (
                f"Observed facts about the image (use only these):\n{facts}\n\n{instruction}")
        return apply_domain_brief(instruction, domain_brief)

    base = _COMPOSE_PROMPT_STYLE if style_mode else _COMPOSE_PROMPT_CONCEPT
    return apply_domain_brief(
        base
        .replace("{facts_section}", _facts_section(facts))
        .replace("{annotations_section}", _annotations_section(bbox_annotations))
        .replace("{concept_token}", concept_token or ""),
        domain_brief,
    )


def build_gap_prompt(draft: str) -> str:
    """Stage C: ask only for what the draft omits — never for a rewritten caption.

    The reply is a phrase list, merged into the draft by :mod:`.gap_fill`. Needs
    neither the concept token nor the style flag: nothing about the existing
    caption is regenerated, so nothing about it can be lost.
    """
    return _GAP_PROMPT.replace("{draft}", draft)
