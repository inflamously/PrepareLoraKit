"""Caption text inspection and cleanup: boilerplate, length/token checks, and coverage."""
from __future__ import annotations

import re

# Function words carry no visual content, so they never count towards coverage.
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "behind", "beside", "by", "for",
    "from", "in", "into", "is", "it", "its", "of", "on", "or", "over", "that",
    "the", "their", "there", "this", "to", "under", "up", "with", "within",
})

_WORD_RE = re.compile(r"[a-z0-9]+")


def singular(word: str) -> str:
    """Crude plural fold so "curtains" and "curtain" compare equal."""
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def content_words(text: str) -> set[str]:
    """Lowercased, de-pluralised content words of ``text``, stopwords removed."""
    return {
        singular(word)
        for word in _WORD_RE.findall((text or "").lower())
        if word not in _STOPWORDS
    }


def covered(haystack: str, phrase: str) -> bool:
    """True when every content word of ``phrase`` already appears in ``haystack``.

    The right test before *adding* a short phrase, where a near-miss is usually a
    genuinely new detail. A phrase with no content words at all counts as covered —
    there is nothing in it worth adding.
    """
    words = content_words(phrase)
    if not words:
        return True
    return words <= content_words(haystack)


# Prepositions end the base noun phrase: in "a chipped mug with a blue rim", the thing
# being named is the mug, not the rim.
_PREPOSITIONS = frozenset({
    "about", "above", "across", "against", "along", "amid", "among", "around", "at",
    "atop", "before", "behind", "below", "beneath", "beside", "between", "beyond",
    "by", "down", "during", "for", "from", "in", "inside", "into", "near", "of",
    "off", "on", "onto", "outside", "over", "past", "through", "to", "toward",
    "under", "underneath", "up", "upon", "with", "within", "without",
})


def head_noun(phrase: str) -> str | None:
    """The thing ``phrase`` names — the head of its base noun phrase.

    Approximated as the last content word before the first preposition or comma,
    which is where an English noun phrase stops naming and starts qualifying:
    ``"a chipped enamel mug with a blue rim"`` → ``"mug"``.
    """
    base = (phrase or "").split(",")[0]
    head = None
    for word in _WORD_RE.findall(base.lower()):
        if word in _PREPOSITIONS:
            break
        if word not in _STOPWORDS:
            head = word
    return singular(head) if head else None


def mentions(haystack: str, phrase: str) -> bool:
    """True when ``haystack`` refers to the thing ``phrase`` names.

    Much weaker than :func:`covered`, and deliberately so. It answers "has this
    region been described at all?", not "was it described exactly?" — compose is
    asked to weave labels in *naturally*, so a paraphrase that keeps the head noun
    and drops the modifiers is the expected outcome, not a failure. Treating that
    as missing and re-appending the full label makes the caption describe the same
    thing twice, once vaguely and once precisely, which is worse than the paraphrase.
    """
    head = head_noun(phrase)
    if head is None:
        return True
    return head in content_words(haystack)


_BOILERPLATE = [
    re.compile(r"^(this image (shows?|depicts?|features?|captures?|presents?)[,:]?\s*)", re.I),
    re.compile(
        r"^(the (photo|photograph|image|picture) (shows?|depicts?|features?|captures?)[,:]?\s*)",
        re.I),
    re.compile(r"^(in this (image|photo|photograph|picture)[,:]?\s*)", re.I),
    re.compile(r"^(here (we see|is)[,:]?\s*)", re.I),
    re.compile(
        r"^(a (photo|photograph|image|picture) (of|showing|depicting|featuring)[,:]?\s*)",
        re.I),
    re.compile(
        r"\s*\(?(generated|ai.?generated|stock photo|getty images?|shutterstock)[^.]*\.?\s*$",
        re.I),
]


# Reasoning ("thinking") models emit their chain of thought inline, ahead of the
# answer. The markers are ordinary vocabulary tokens, so `skip_special_tokens=True`
# does not remove them — and even where it did, the reasoning *prose* between them
# is plain text that would land verbatim in the training .txt file.
_THINK_TAG = r"(?:think|thinking|thought)"
_THINK_BLOCK_RE = re.compile(rf"<{_THINK_TAG}\s*>.*?</{_THINK_TAG}\s*>", re.I | re.S)
_THINK_LEAD_RE = re.compile(rf"^.*</{_THINK_TAG}\s*>", re.I | re.S)
_THINK_OPEN_RE = re.compile(rf"<{_THINK_TAG}\s*>.*$", re.I | re.S)


def strip_reasoning(text: str) -> str:
    """Remove a reasoning model's chain of thought, keeping only its answer.

    Three shapes have to be handled, and the order below is what makes them
    compose:

    1. A complete ``<think>…</think>`` block before the answer.
    2. A stray closing tag with no opener — chat templates that enable thinking
       append ``<think>`` to the *prompt*, so generation starts inside the block
       and only ``</think>`` is ever decoded.
    3. A stray opening tag with no close — ``max_new_tokens`` ran out mid-thought.
       Everything after it is reasoning, so the result is empty: there was no
       answer in the output at all, and a truncated thought is not a caption.
    """
    text = (text or "").strip()
    if not text:
        return ""
    text = _THINK_BLOCK_RE.sub("", text)
    text = _THINK_LEAD_RE.sub("", text)
    text = _THINK_OPEN_RE.sub("", text)
    return text.strip()


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
