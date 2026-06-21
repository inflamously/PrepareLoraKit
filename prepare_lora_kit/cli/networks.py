"""`networks` / `network-types` commands — inspect network profiles and adapter types."""
from __future__ import annotations

from ..networks import registry
from ._shared import cli


@cli.command()
def networks():
    """List available network profiles and their default adapter type."""
    from ..utils.report import console
    from rich.table import Table
    from rich import box

    names = registry.list_networks()
    t = Table(title="Available Network Profiles", box=box.SIMPLE)
    t.add_column("Name", style="cyan")
    t.add_column("Adapter type", style="magenta")
    for n in names:
        try:
            prof = registry.load(n)
            ntype = (prof.config_template.get("network") or {}).get("type", "lora")
        except Exception:
            ntype = "?"
        t.add_row(n, ntype)
    console.print(t)


@cli.command(name="network-types")
def network_types():
    """List supported adapter-network types (lora / lokr / dora) and their defaults."""
    from ..utils.report import console
    from ..networks.net_types import NET_TYPE_MAP
    from ..networks.config import NetworkConfig
    from rich.table import Table
    from rich import box

    t = Table(title="Supported Adapter-Network Types", box=box.SIMPLE)
    t.add_column("Type", style="cyan")
    t.add_column("ai-toolkit class", style="magenta")
    t.add_column("Default params", style="green")
    for name, spec in NET_TYPE_MAP.items():
        defaults = NetworkConfig.from_dict({"type": name}).to_toolkit_dict()
        defaults.pop("type", None)
        params = ", ".join(f"{k}={v}" for k, v in defaults.items())
        t.add_row(name, spec.toolkit_class, params or "—")
    console.print(t)
