"""Additive gap-fill for a drafted caption: gate → parse → merge.

The third grounded pass used to hand the whole draft back to the VLM and ask for
"the corrected caption". Because the *output format* was a full caption, the model
rewrote freely — paraphrasing human-authored region labels, reordering attributes
and dropping detail. No prompt wording can prevent that; the contract has to change.

Here the model is asked only for a short list of elements the draft is missing, and
the merge happens in Python. That makes the pass additive **by construction** (it
never sees a chance to emit a replacement), roughly an order of magnitude cheaper to
decode, and auditable.

:func:`needs_gap_pass` gates the extra generation on cheap text signals so a good
draft costs nothing at all — on a VLM the expensive part of any pass is re-encoding
the image, so skipping the pass is the only real saving.
"""
from __future__ import annotations

import re

from prepare_lora_kit.steps.caption_bbox.caption_text import covered, mentions

# The compose stage targets a 20–80 word caption; below the floor it has almost
# certainly under-described the image.
_MIN_WORDS = 20

# Filler the compose prompt explicitly bans. Its presence means the model ignored
# the instruction and reached for generic vocabulary — a reliable smell for a
# caption that describes nothing in particular.
_LOW_INFORMATION_TERMS = (
    "some kind of", "a type of", "a sort of", "various", "several objects",
    "an object", "a scene", "something", "unidentified", "unknown",
    "detailed", "beautiful", "realistic", "high quality", "stunning",
    "intricate", "etc",
)
_LOW_INFORMATION_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in _LOW_INFORMATION_TERMS) + r")\b",
    re.IGNORECASE,
)

_LIST_MARKER_RE = re.compile(r"^\s*(?:[-*•–—]+|\d+[.)])\s*")
_QUOTES = "\"'“”‘’"


def needs_gap_pass(
        draft: str,
        annotation_lines: list[dict] | tuple = (),
        *,
        min_words: int = _MIN_WORDS,
) -> str | None:
    """Return why ``draft`` warrants a gap pass, or ``None`` to skip it.

    The reason string is for reporting and logs; callers only need the truthiness.
    """
    text = (draft or "").strip()
    if len(text.split()) < min_words:
        return "short_caption"

    for ann in annotation_lines or ():
        label = (ann.get("label") if isinstance(ann, dict) else ann) or ""
        label = str(label).strip()
        # Same lenient test validation.enforce_region_labels uses, so the gate never
        # spends a pass chasing a label that enforcement would consider present.
        if label and not mentions(text, label):
            return "missing_label"

    if _LOW_INFORMATION_RE.search(text):
        return "low_information"
    return None


def parse_gap_phrases(raw: str, *, max_phrases: int = 3, max_words: int = 8) -> list[str]:
    """Extract the missing-element phrases from the gap pass's raw output.

    Tolerates the formatting models add unbidden (bullets, numbering, quotes, a
    repeated header) and discards anything that is not a short noun phrase — a
    model that answers with prose is answering the wrong question, and its output
    must not reach the caption.
    """
    phrases: list[str] = []
    for line in (raw or "").splitlines():
        line = _LIST_MARKER_RE.sub("", line.strip()).strip().strip(_QUOTES).strip()
        if not line:
            continue
        bare = line.strip(" .,:;!").lower()
        if not bare:
            continue
        if bare == "none":
            break
        if line.endswith(":"):           # echoed header, e.g. "Missing elements:"
            continue
        if "caption" in bare:            # meta-commentary about the draft itself
            continue
        if len(bare.split()) > max_words:
            continue
        phrases.append(line.strip(" .,;"))
        if len(phrases) >= max_phrases:
            break
    return phrases


def _decapitalise(phrase: str) -> str:
    """Lower the leading capital of an appended phrase, sparing proper nouns.

    A phrase whose first word is an acronym ("LED strip") or that capitalises any
    later word ("Eiffel Tower") is left alone; otherwise the leading capital is
    sentence-start artefact and would read wrong mid-caption.
    """
    words = phrase.split()
    if not words:
        return phrase
    if len(words[0]) > 1 and words[0].isupper():
        return phrase
    if any(word[:1].isupper() for word in words[1:]):
        return phrase
    return phrase[0].lower() + phrase[1:]


def merge_missing_phrases(
        caption: str,
        phrases: list[str],
        *,
        max_chars: int = 600,
) -> str:
    """Append the phrases that are genuinely missing; never remove or reword.

    ``max_chars`` mirrors the ceiling :func:`..prompts.caption_length_ok` validates
    against, so gap-fill can never push a caption into the "very long" bucket.
    """
    merged = (caption or "").strip()
    if not phrases:
        return merged

    trailing_period = merged.endswith(".")
    body = merged.rstrip(" .,;")
    appended = False

    for phrase in phrases:
        phrase = (phrase or "").strip().strip(_QUOTES).strip(" .,;")
        if not phrase or covered(body, phrase):
            continue
        candidate = f"{body}, {_decapitalise(phrase)}"
        if len(candidate) + (1 if trailing_period else 0) > max_chars:
            continue
        body = candidate
        appended = True

    if not appended:
        return merged
    return f"{body}." if trailing_period else body
