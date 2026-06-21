"""
NetworkConfig — generic, ai-toolkit-style adapter-network configuration.

A single schema that covers every supported adapter type (lora / lokr / dora) via
a ``type`` field plus a ``network_kwargs`` catch-all for type-specific extras. This
mirrors ostris/ai-toolkit's ``toolkit.config_modules.NetworkConfig``.

This is the *adapter* network (the trainable LoRA/LoKr/DoRA), NOT the base-model
``NetworkProfile`` in ``base.py``. The supported types live in ``net_types.py``.

The config is parsed from a profile's ``config_template.network`` block (and an
optional per-run ``type`` override) and rendered, via ``to_toolkit_dict()``, into the
``config.process[0].network`` section of the generated ai-toolkit training YAML.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NetworkConfig:
    type: str = "lora"                  # one of net_types.KNOWN_NET_TYPES
    linear: int = 16                    # rank; from_dict accepts the alias `rank`
    linear_alpha: int = 16              # alpha; alias `alpha`; defaults to `linear`
    conv: int | None = None             # conv rank; None → omitted
    conv_alpha: int | None = None       # conv alpha; defaults to `conv` when conv set
    dropout: float | None = None        # network dropout; None → omitted
    # None (not True) so the key is omitted unless explicitly set — keeps existing
    # profiles' rendered output byte-identical. ai-toolkit defaults this to True itself.
    transformer_only: bool | None = None
    # lokr-specific (emitted only when type == "lokr")
    lokr_full_rank: bool = False
    lokr_factor: int = -1
    # generic per-type pass-through (ignore_if_contains, only_if_contains,
    # rank_dropout, module_dropout, ...); emitted verbatim under `network_kwargs`.
    network_kwargs: dict[str, Any] = field(default_factory=dict)

    # ── construction ─────────────────────────────────────────────────────────
    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "NetworkConfig":
        """Parse a raw ``network`` block into a validated ``NetworkConfig``.

        Tolerant of the ``rank``/``alpha`` aliases and of unknown keys (folded into
        ``network_kwargs``). Validates ``type`` against the registry.
        """
        from .net_types import KNOWN_NET_TYPES  # local import: avoids an import cycle

        d = dict(d or {})  # never mutate the caller's dict

        # alias coercion: rank → linear, alpha → linear_alpha (explicit field wins)
        if "rank" in d:
            d.setdefault("linear", d.pop("rank"))
        else:
            d.pop("rank", None)
        if "alpha" in d:
            d.setdefault("linear_alpha", d.pop("alpha"))
        else:
            d.pop("alpha", None)

        ntype = d.get("type", "lora")
        if ntype not in KNOWN_NET_TYPES:
            raise ValueError(
                f"Unknown network type '{ntype}'. "
                f"Known: {', '.join(sorted(KNOWN_NET_TYPES))}"
            )

        # alpha defaults to linear; conv_alpha defaults to conv (when conv given)
        if "linear_alpha" not in d and "linear" in d:
            d["linear_alpha"] = d["linear"]
        if d.get("conv") is not None and "conv_alpha" not in d:
            d["conv_alpha"] = d["conv"]

        # Fold unknown keys into network_kwargs rather than crashing (tolerant parse,
        # matching the style of the other from_yaml/from_dict loaders).
        known = set(cls.__dataclass_fields__)
        nk = dict(d.pop("network_kwargs", {}) or {})
        for k in list(d):
            if k not in known:
                nk[k] = d.pop(k)
        d["network_kwargs"] = nk

        obj = cls(**d)
        obj._validate()
        return obj

    def _validate(self) -> None:
        if self.linear < 1:
            raise ValueError(f"network.linear (rank) must be >= 1, got {self.linear}")
        if self.linear_alpha < 1:
            raise ValueError(f"network.linear_alpha must be >= 1, got {self.linear_alpha}")
        if self.conv is not None and self.conv < 1:
            raise ValueError(f"network.conv must be >= 1 or null, got {self.conv}")
        if self.dropout is not None and not (0.0 <= self.dropout < 1.0):
            raise ValueError(f"network.dropout must be in [0, 1), got {self.dropout}")
        if self.type == "lokr" and self.lokr_factor == 0:
            raise ValueError("network.lokr_factor must be -1 (auto) or a positive int")

    def with_rank_alpha(self, rank: int, alpha: int) -> "NetworkConfig":
        """Return a copy with per-run rank/alpha overlaid (used by step 7's build)."""
        c = copy.deepcopy(self)
        c.linear, c.linear_alpha = rank, alpha
        c._validate()
        return c

    # ── rendering ────────────────────────────────────────────────────────────
    def to_toolkit_dict(self) -> dict[str, Any]:
        """Render the ``config.process[0].network`` dict for the ai-toolkit YAML.

        Optional fields are gated by the type's ``relevant_fields`` so an overridden
        type emits a clean, type-appropriate block (e.g. lokr drops conv and adds the
        lokr_* keys; lora/dora keep conv).
        """
        from .net_types import NET_TYPE_MAP

        relevant = NET_TYPE_MAP[self.type].relevant_fields
        out: dict[str, Any] = {
            "type": self.type,
            "linear": self.linear,
            "linear_alpha": self.linear_alpha,
        }
        if "conv" in relevant and self.conv is not None:
            out["conv"] = self.conv
            out["conv_alpha"] = self.conv_alpha if self.conv_alpha is not None else self.conv
        if "dropout" in relevant and self.dropout is not None:
            out["dropout"] = self.dropout
        if "transformer_only" in relevant and self.transformer_only is not None:
            out["transformer_only"] = self.transformer_only
        if "lokr_full_rank" in relevant:
            out["lokr_full_rank"] = self.lokr_full_rank
        if "lokr_factor" in relevant:
            out["lokr_factor"] = self.lokr_factor
        if self.network_kwargs:
            out["network_kwargs"] = dict(self.network_kwargs)
        return out
