"""Word-level caption diff between a baseline run and a candidate run."""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Literal

DiffOp = Literal["same", "added", "removed"]
_EDGE_PUNCTUATION = ".,;:!?\"'()"


@dataclass(frozen=True)
class DiffToken:
    text: str
    op: DiffOp


def _key(word: str) -> str:
    """Comparison key: case and edge punctuation are noise in a caption diff."""
    return word.strip(_EDGE_PUNCTUATION).lower()


def word_diff(baseline: str, candidate: str) -> list[DiffToken]:
    """Tokens of ``candidate`` interleaved with the ``baseline`` words it dropped.

    Within a replaced span, removed words come before added ones, so reading the
    output left to right shows "what was there, then what replaced it".
    """
    old, new = (baseline or "").split(), (candidate or "").split()
    matcher = difflib.SequenceMatcher(
        a=[_key(w) for w in old], b=[_key(w) for w in new], autojunk=False,
    )
    tokens: list[DiffToken] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            tokens.extend(DiffToken(w, "same") for w in new[j1:j2])
            continue
        tokens.extend(DiffToken(w, "removed") for w in old[i1:i2])
        tokens.extend(DiffToken(w, "added") for w in new[j1:j2])
    return tokens
