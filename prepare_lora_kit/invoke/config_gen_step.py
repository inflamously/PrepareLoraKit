"""Invoke adapter for ConfigGenStep."""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from prepare_lora_kit_pipeline.configs.config_gen_config import ConfigGenConfig

from .working_dataset import _require_working_dataset


def _invoke_ConfigGenStep(working_dir: Path, output_dir: Path, cfg: ConfigGenConfig,
                          *, network, concept_token: Optional[str],
                          network_type: Optional[str] = None, **_kw) -> None:
    _require_working_dataset(working_dir)
    from ..steps import training_config
    training_config.run(
        working_dir,
        network=network,
        concept_token=concept_token,
        output_dir=output_dir,
        network_type=network_type,
        report_path=output_dir / "reports" / "ConfigGenStep_report.json",
        enabled_substeps=_kw.get("enabled_substeps"),
        cancel_check=_kw.get("cancel_check"),
    )
