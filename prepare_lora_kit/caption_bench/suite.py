"""A benchmark suite: a folder of images plus ``bench.yaml`` describing each case.

Layout::

    <suite>/
      bench.yaml          # name, concept_token, defaults, images
      images/…            # the images (default case list when ``images`` is omitted)
      variants/<name>.yaml
      runs/<run_id>.json  # written by ``store``

``bench.yaml``::

    name: food
    concept_token: krustekrabbe        # suite default; a case may override or null it
    defaults:                          # CaptionBboxConfig overrides for every variant
      caption_model_id: Qwen/Qwen3-VL-8B-Instruct
    images:
      - path: images/burger.png
        notes: invented food item
        annotations:                   # same shape as the step's boxes sidecar
          - {label: sesame claws, x1: 0.1, y1: 0.1, x2: 0.4, y2: 0.4}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SUITE_FILE = "bench.yaml"
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})
_BOX_KEYS = ("x1", "y1", "x2", "y2")
# Sentinel: a case that does not mention ``concept_token`` inherits the suite's,
# while an explicit ``concept_token: null`` means "style mode for this image".
_INHERIT = object()


@dataclass(frozen=True)
class BenchCase:
    """One image to caption, with the inputs the real step would give it."""

    image: Path
    rel_path: str
    concept_token: str | None = None
    annotations: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""

    @property
    def name(self) -> str:
        return self.image.name


@dataclass(frozen=True)
class BenchSuite:
    """A loaded benchmark suite."""

    root: Path
    name: str
    cases: list[BenchCase]
    defaults: dict[str, Any] = field(default_factory=dict)

    @property
    def variants_dir(self) -> Path:
        return self.root / "variants"

    @property
    def runs_dir(self) -> Path:
        return self.root / "runs"

    @classmethod
    def load(cls, root: Path) -> BenchSuite:
        return _SuiteLoader(Path(root)).load()


class _SuiteLoader:
    """Parses and validates ``bench.yaml``, naming the offending image on error."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def load(self) -> BenchSuite:
        data = self._read()
        default_token = _clean_token(data.get("concept_token"))
        entries = data.get("images")
        cases = (
            [self._case(entry, default_token) for entry in entries]
            if entries
            else self._discovered_cases(default_token)
        )
        defaults = data.get("defaults") or {}
        if not isinstance(defaults, dict):
            raise ValueError(f"{SUITE_FILE}: 'defaults' must be a mapping")
        return BenchSuite(
            root=self.root,
            name=str(data.get("name") or self.root.name),
            cases=cases,
            defaults=dict(defaults),
        )

    def _read(self) -> dict[str, Any]:
        path = self.root / SUITE_FILE
        if not path.is_file():
            raise ValueError(
                f"No {SUITE_FILE} in benchmark suite {self.root} — create one with "
                "`plk caption-bench init`"
            )
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"{path}: expected a mapping at the top level")
        return data

    def _discovered_cases(self, token: str | None) -> list[BenchCase]:
        images_dir = self.root / "images"
        paths = sorted(
            p for p in images_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
        ) if images_dir.is_dir() else []
        return [
            BenchCase(image=p, rel_path=p.relative_to(self.root).as_posix(), concept_token=token)
            for p in paths
        ]

    def _case(self, entry: Any, default_token: str | None) -> BenchCase:
        if isinstance(entry, str):
            entry = {"path": entry}
        if not isinstance(entry, dict) or not entry.get("path"):
            raise ValueError(f"{SUITE_FILE}: every image entry needs a 'path'")
        rel = str(entry["path"])
        image = (self.root / rel).resolve()
        if not image.is_file():
            raise ValueError(f"{SUITE_FILE}: image not found: {rel}")
        token = entry.get("concept_token", _INHERIT)
        return BenchCase(
            image=image,
            rel_path=Path(rel).as_posix(),
            concept_token=default_token if token is _INHERIT else _clean_token(token),
            annotations=[_annotation(raw, rel) for raw in entry.get("annotations") or []],
            notes=str(entry.get("notes") or ""),
        )


def _clean_token(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip() or None


def _annotation(raw: Any, rel: str) -> dict[str, Any]:
    """Normalise one annotation to the runtime's ``{label, x1..y2}`` shape."""
    try:
        box = {key: float(raw[key]) for key in _BOX_KEYS}
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"{SUITE_FILE}: annotation on {rel} needs numeric x1, y1, x2, y2: {raw!r}"
        ) from exc
    return {"label": str(raw.get("label") or "").strip(), **box}
