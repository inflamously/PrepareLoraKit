"""Global caption prompt library: list/load/save/delete named prompts.

Prompts are stored as one YAML file per entry under ``configs/caption_prompts/``,
mirroring the project/network registries (see :mod:`..project.registry`). The
library is *global* — shared across every project — so a prompt saved once can be
reused for any run.

Two kinds exist:

* ``full_image`` — the per-image caption instruction (the full-image template).
* ``region``     — the bbox crop caption instruction.

A prompt's ``text`` is a template that may contain ``{bbox_annotations}`` and
``{concept_token}`` placeholders; these are filled in at caption time by
:func:`..utils.caption.apply_prompt_placeholders`. Filenames are namespaced by
kind (``<kind>__<slug>.yaml``) so the same name can exist for both kinds.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from ..paths import CONFIGS_DIR

KINDS = ("full_image", "region")
_PROMPTS_DIR = CONFIGS_DIR / "caption_prompts"


@dataclass
class CaptionPrompt:
    """One named caption prompt in the global library."""

    name: str
    kind: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "kind": self.kind, "text": self.text}

    @classmethod
    def from_yaml(cls, path: Path) -> "CaptionPrompt":
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(
            name=str(data.get("name", path.stem)),
            kind=str(data.get("kind", "full_image")),
            text=str(data.get("text", "")),
        )


def _validate_kind(kind: str) -> str:
    if kind not in KINDS:
        raise ValueError(
            f"Unknown caption prompt kind '{kind}'. Expected one of {list(KINDS)}."
        )
    return kind


def _slug(name: str) -> str:
    safe = name.strip().lower().replace("-", "_").replace(" ", "_")
    return "".join(c for c in safe if c.isalnum() or c == "_")


def _path_for(kind: str, name: str) -> Path:
    return _PROMPTS_DIR / f"{kind}__{_slug(name)}.yaml"


def list_prompts(kind: str) -> list[CaptionPrompt]:
    """Return all saved prompts of ``kind``, sorted by name."""
    _validate_kind(kind)
    if not _PROMPTS_DIR.exists():
        return []
    prompts: list[CaptionPrompt] = []
    for path in sorted(_PROMPTS_DIR.glob(f"{kind}__*.yaml")):
        try:
            prompt = CaptionPrompt.from_yaml(path)
        except Exception:
            continue
        if prompt.kind == kind:
            prompts.append(prompt)
    prompts.sort(key=lambda p: p.name.lower())
    return prompts


def load(kind: str, name: str) -> CaptionPrompt:
    """Load a single prompt by kind + name. Raises if it does not exist."""
    _validate_kind(kind)
    path = _path_for(kind, name)
    if not path.exists():
        raise ValueError(f"Unknown {kind} caption prompt '{name}'.")
    return CaptionPrompt.from_yaml(path)


def save(kind: str, name: str, text: str) -> CaptionPrompt:
    """Create or overwrite a named prompt. Returns the saved entry."""
    _validate_kind(kind)
    name = name.strip()
    if not name:
        raise ValueError("Caption prompt name is required.")
    prompt = CaptionPrompt(name=name, kind=kind, text=str(text))
    _PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    _path_for(kind, name).write_text(
        yaml.safe_dump(prompt.to_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return prompt


def delete(kind: str, name: str) -> None:
    """Remove a named prompt (idempotent)."""
    _validate_kind(kind)
    _path_for(kind, name).unlink(missing_ok=True)
