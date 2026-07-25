"""Shared caption text normalisation.

Both caption stages that compare two pieces of caption text need the same notion of
"does this already say that?": :mod:`.gap_fill` before appending a phrase, and
:mod:`.grounded` before accepting a human's region labels in place of an observation
pass. Kept apart from :mod:`.prompts` so neither has to import prompt templates just
to compare two strings.

The comparison is deliberately loose — content words only, plurals folded. In both
call sites a false "already covered" merely skips an addition, while a false "not
covered" duplicates text and dilutes the caption for the text encoder.
"""
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

    A phrase with no content words at all counts as covered — there is nothing in
    it worth adding.
    """
    words = content_words(phrase)
    if not words:
        return True
    return words <= content_words(haystack)
