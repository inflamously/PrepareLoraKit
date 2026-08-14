"""Durable per-image caption verdicts, shared by CaptionVerifierStep and CaptionBboxStep.

``resolved`` has exactly one meaning: the caption this verdict judged has since been
replaced. A resolved entry stops flagging, reopening and seeding the review modal,
while the verdict text is kept forever as history.
"""
from __future__ import annotations

import json
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prepare_lora_kit.report import reporter

LEDGER_NAME = "caption_verdicts.json"
VERDICTS = ("correct", "generic", "wrong")
# The two that mean "this caption needs work". ``correct`` is the no-op default
# the review modal lands every unjudged item on, so it must never reopen.
FLAGGED_VERDICTS = ("generic", "wrong")
_VERSION = 1


@dataclass
class VerdictEntry:
    """One image's standing judgement."""

    verdict: str
    caption_at_verdict: str = ""
    updated_at: str | None = None
    resolved: bool = False

    @property
    def flagged(self) -> bool:
        """Still needs a fix: a bad verdict whose caption has not been replaced."""
        return self.verdict in FLAGGED_VERDICTS and not self.resolved

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "caption_at_verdict": self.caption_at_verdict,
            "updated_at": self.updated_at,
            "resolved": self.resolved,
        }

    @classmethod
    def from_dict(cls, data: Any) -> VerdictEntry | None:
        """Build one entry, or ``None`` if the row is unusable.

        Returning ``None`` rather than raising lets a single corrupt row be
        dropped without discarding every other verdict in the file.
        """
        if not isinstance(data, dict):
            return None
        verdict = data.get("verdict")
        if verdict not in VERDICTS:
            return None
        return cls(
            verdict=str(verdict),
            caption_at_verdict=str(data.get("caption_at_verdict") or ""),
            updated_at=data.get("updated_at") or None,
            resolved=bool(data.get("resolved", False)),
        )


class VerdictLedger:
    """Load-mutate-save document of caption verdicts under a reports directory.

    Construct it with the directory the step's report lands in — never with the
    step's ``output_dir``, which for both callers can be the dataset directory
    when no explicit report path was given.
    """

    def __init__(self, reports_dir: Path) -> None:
        self._path = Path(reports_dir) / LEDGER_NAME
        self._dirty = False
        self._entries: dict[str, VerdictEntry] = self._load()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self) -> dict[str, VerdictEntry]:
        if not self._path.is_file():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            reporter.warn(f"Ignoring unreadable caption verdict ledger: {self._path}")
            # Dirty so the next save replaces the damaged file with a valid one
            # rather than leaving it to fail the same way on every future run.
            self._dirty = True
            return {}

        rows, legacy = self._rows(raw)
        entries: dict[str, VerdictEntry] = {}
        for key, value in rows.items():
            entry = VerdictEntry.from_dict(value)
            if entry is not None:
                entries[str(key)] = entry
        # Dirty on a legacy shape or a dropped row, so the next save replaces the
        # file with a clean, current-format document instead of re-parsing it.
        if legacy or len(entries) != len(rows):
            self._dirty = True
        return entries

    @staticmethod
    def _rows(raw: Any) -> tuple[dict[str, Any], bool]:
        """Split a loaded document into its rows plus "was it the legacy shape".

        Accepts both the wrapped ``{version, entries}`` document and a bare
        path->entry mapping, which is what a hand-written or prototype ledger
        looks like.
        """
        if not isinstance(raw, dict):
            return {}, False
        entries = raw.get("entries")
        if isinstance(entries, dict):
            return entries, False
        if "version" in raw:
            return {}, False
        return raw, True

    def save(self) -> None:
        """Write the document atomically; a no-op when nothing changed."""
        if not self._dirty:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "version": _VERSION,
            "entries": {key: entry.to_dict() for key, entry in self._entries.items()},
        }
        # tmp + os.replace in the same directory, matching captions.py's caption
        # write-back: a half-written ledger would strand flagged images.
        tmp = self._path.with_name(f".{self._path.name}.plk_tmp")
        tmp.write_text(json.dumps(document, indent=2), encoding="utf-8")
        tmp.replace(self._path)
        self._dirty = False

    # ── lookup ───────────────────────────────────────────────────────────────

    def entry_for(self, image_path: Path | str) -> VerdictEntry | None:
        key = self._match(image_path)
        return self._entries.get(key) if key else None

    def verdict_for(self, image_path: Path | str) -> str | None:
        """The verdict still in force, or ``None`` when absent or resolved."""
        entry = self.entry_for(image_path)
        return entry.verdict if entry is not None and not entry.resolved else None

    def is_flagged(self, image_path: Path | str) -> bool:
        entry = self.entry_for(image_path)
        return entry is not None and entry.flagged

    def flagged(self, image_paths: Iterable[Path]) -> dict[Path, str]:
        """Flagged verdicts keyed by the caller's own ``Path`` objects.

        Callers hold unresolved paths from ``iter_images`` and test membership
        with them directly, so the normalization happens here once instead of at
        every ``path in flagged`` site.
        """
        found: dict[Path, str] = {}
        for path in image_paths:
            entry = self.entry_for(path)
            if entry is not None and entry.flagged:
                found[path] = entry.verdict
        return found

    # ── mutation ─────────────────────────────────────────────────────────────

    def record(
            self,
            image_path: Path | str,
            verdict: str,
            *,
            caption: str = "",
            resolved: bool = False,
    ) -> None:
        """Store a fresh judgement, replacing any previous one for this image."""
        if verdict not in VERDICTS:
            return
        self._entries[self._key_for(image_path)] = VerdictEntry(
            verdict=verdict,
            caption_at_verdict=str(caption or ""),
            updated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            resolved=resolved,
        )
        self._dirty = True

    def mark_resolved(self, image_paths: Iterable[str | Path]) -> int:
        """Flag the captions these images now carry as replaced.

        Never creates entries: an image with no verdict has nothing to resolve.
        Returns how many entries actually changed, so callers can skip the save.
        """
        changed = 0
        for path in image_paths:
            key = self._match(path)
            entry = self._entries.get(key) if key else None
            if entry is None or entry.resolved:
                continue
            entry.resolved = True
            changed += 1
        if changed:
            self._dirty = True
        return changed

    # ── key matching ─────────────────────────────────────────────────────────

    @staticmethod
    def _key_for(image_path: Path | str) -> str:
        """Canonical ledger key: the resolved absolute path, as a string."""
        try:
            return str(Path(image_path).resolve())
        except OSError:
            return str(image_path)

    def _match(self, image_path: Path | str) -> str | None:
        """Find this image's key, tolerating a relocated output directory.

        The resolved path is the real lookup. The basename fallback exists so a
        re-created or moved ``outputs/<project>/`` does not silently lose every
        verdict, and is refused when the name is ambiguous — a dataset with
        mirrored subdirectories can hold several ``a.png``, and flagging the
        wrong one would send the user to re-caption a good image.
        """
        key = self._key_for(image_path)
        if key in self._entries:
            return key
        name = Path(image_path).name
        matches = [k for k in self._entries if Path(k).name == name]
        return matches[0] if len(matches) == 1 else None
