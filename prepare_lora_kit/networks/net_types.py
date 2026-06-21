"""
Adapter-network type registry (ai-toolkit style).

Declares the supported adapter-network *types* (the trainable LoRA/LoKr/DoRA),
each with the set of config fields that are meaningful for it. This is the single
place new types are registered — mirrors the ``STEP_TYPE_MAP`` pattern in
``project/base.py``.

NOTE: this is the *adapter* network, not the base-model ``NetworkProfile`` in
``base.py``. See ``config.py`` for the ``NetworkConfig`` schema that uses this map.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class NetTypeSpec:
    """Declares the relevant fields (and an informational class hint) for one type."""
    name: str
    toolkit_class: str               # ai-toolkit module/class hint; surfaced in the CLI
    relevant_fields: tuple[str, ...]  # gates NetworkConfig.to_toolkit_dict() emission


# Fields shared by every adapter type. Type-specific fields are appended per entry.
_COMMON: tuple[str, ...] = (
    "type", "linear", "linear_alpha", "transformer_only", "dropout", "network_kwargs",
)

NET_TYPE_MAP: dict[str, NetTypeSpec] = {
    "lora": NetTypeSpec("lora", "LoRANetwork", _COMMON + ("conv", "conv_alpha")),
    "lokr": NetTypeSpec("lokr", "LoKrNetwork", _COMMON + ("lokr_full_rank", "lokr_factor")),
    "dora": NetTypeSpec("dora", "DoRANetwork", _COMMON + ("conv", "conv_alpha")),
}

KNOWN_NET_TYPES = frozenset(NET_TYPE_MAP)


def list_network_types() -> list[str]:
    """Return the supported adapter-network type names, sorted."""
    return sorted(NET_TYPE_MAP)
