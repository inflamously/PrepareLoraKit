"""Benchmark variants: named ``CaptionBboxConfig`` overrides compared side by side."""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

import yaml

from prepare_lora_kit.caption_bench.suite import BenchSuite
from prepare_lora_kit.pipeline.configs import CaptionBboxConfig

#: Always available: the suite defaults on top of today's built-in config, i.e. the
#: baseline every prompt change gets measured against.
CURRENT = "current"

_CONFIG_FIELDS = frozenset(f.name for f in dataclasses.fields(CaptionBboxConfig))


@dataclass(frozen=True)
class BenchVariant:
    """One named configuration to caption the suite with."""

    name: str
    overrides: dict[str, Any]
    config: CaptionBboxConfig


def available_variants(suite: BenchSuite) -> list[str]:
    """``current`` plus every ``variants/<name>.yaml`` in the suite."""
    names = {CURRENT}
    if suite.variants_dir.is_dir():
        names.update(p.stem for p in suite.variants_dir.glob("*.yaml"))
    return sorted(names)


def load_variants(
    suite: BenchSuite,
    names: list[str],
    *,
    model_id: str | None = None,
) -> list[BenchVariant]:
    """Resolve ``names`` to configs: suite defaults < variant file < ``model_id``."""
    return [_load_variant(suite, name, model_id) for name in names]


def _load_variant(suite: BenchSuite, name: str, model_id: str | None) -> BenchVariant:
    overrides = {**suite.defaults, **_variant_file(suite, name)}
    if model_id:
        overrides["caption_model_id"] = model_id
    unknown = sorted(set(overrides) - _CONFIG_FIELDS)
    if unknown:
        raise ValueError(
            f"Variant '{name}': unknown CaptionBboxConfig setting(s): {', '.join(unknown)}"
        )
    return BenchVariant(name=name, overrides=overrides, config=CaptionBboxConfig(**overrides))


def _variant_file(suite: BenchSuite, name: str) -> dict[str, Any]:
    path = suite.variants_dir / f"{name}.yaml"
    if not path.is_file():
        if name == CURRENT:
            return {}
        raise ValueError(
            f"Unknown variant '{name}'. Available: {', '.join(available_variants(suite))}"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping of CaptionBboxConfig settings")
    return data
