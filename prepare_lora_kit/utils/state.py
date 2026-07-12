"""Pipeline run-state manifest (JSON) for step tracking and resume."""
from __future__ import annotations
from dataclasses import dataclass, field
import json
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

_STEP_MIGRATIONS: dict[str, str | None] = {
    "CaptionStep": "CaptionBboxStep",
    "BucketDryRunStep": "BucketPoolsCheckStep",
}

_SUBSTEP_MIGRATIONS: dict[str, str] = {
    "s0_import": "import_images",
    "s1_1_score": "score_images",
    "s1_2_decide": "review_decisions",
    "s2_1_dupecheck": "duplicate_check",
    "s2_2_clipscan": "clip_scan",
    "s2_3_drop_images": "drop_images",
    "s3_1_select_candidates": "select_upscale_candidates",
    "s3_2_upscale": "upscale_images",
    "s3_3_hallucination_check": "hallucination_check",
    "s5_1_annotate": "annotate_regions",
    "s5_2_caption": "caption_images",
    "s5_3_validate": "validate_captions",
    "s4_1_reconstruct": "reconstruct_images",
    "s4_2_review": "review_vae_artifacts",
    "s4_3_apply_decisions": "apply_vae_decisions",
    "s6_1_pairing": "check_pairing",
    "s6_2_corrupt": "check_corrupt_files",
    "s6_3_caption_quality": "check_caption_quality",
    "s6_4_resolution": "check_resolution",
    "s8_1_assign_buckets": "assign_bucket_pools",
    "s8_2_report_thin_buckets": "report_thin_buckets",
    "s8_3_cache_info": "write_cache_info",
    "s9_1_diff": "preview_export_diff",
    "s9_2_export": "copy_export",
}


@dataclass
class StepState:
    """State of a single pipeline step."""

    status: str
    completed_at: str | None = None
    reason: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"status": self.status}
        if self.completed_at is not None:
            d["completed_at"] = self.completed_at
        if self.reason is not None:
            d["reason"] = self.reason
        d.update(self.meta)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StepState:
        known = {"status", "completed_at", "reason"}
        return cls(
            status=d.get("status", ""),
            completed_at=d.get("completed_at"),
            reason=d.get("reason"),
            meta={k: v for k, v in d.items() if k not in known},
        )


@dataclass
class StateData:
    """Full run-state manifest."""

    steps: dict[str, StepState] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"steps": {k: v.to_dict() for k, v in self.steps.items()}}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StateData:
        steps = {k: StepState.from_dict(v) for k, v in d.get("steps", {}).items()}
        return cls(steps=steps)


class RunState:
    """Tracks which steps completed and stores their output metadata."""

    def __init__(self, dataset_dir: Path):
        self._path = dataset_dir / ".plk_state.json"
        self._data: StateData = self._load()
        if self._migrate_legacy_ids():
            self.save()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self) -> StateData:
        if self._path.exists():
            with open(self._path) as f:
                return StateData.from_dict(json.load(f))
        return StateData()

    def _migrate_legacy_ids(self) -> bool:
        changed = False
        migrated: dict[str, StepState] = {}
        for old_step, state in self._data.steps.items():
            new_step = _STEP_MIGRATIONS.get(old_step, old_step)
            if new_step is None:
                changed = True
                continue
            if new_step != old_step:
                changed = True
            meta = dict(state.meta)
            substeps = meta.get("substeps")
            if isinstance(substeps, dict):
                new_substeps = {}
                for old_substep, value in substeps.items():
                    new_substep = _SUBSTEP_MIGRATIONS.get(old_substep, old_substep)
                    if new_substep != old_substep:
                        changed = True
                    new_substeps[new_substep] = value
                meta["substeps"] = new_substeps
            if meta != state.meta:
                state = StepState(
                    status=state.status,
                    completed_at=state.completed_at,
                    reason=state.reason,
                    meta=meta,
                )
            migrated[new_step] = state
        if migrated != self._data.steps:
            self._data.steps = migrated
            changed = True
        return changed

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._data.to_dict(), f, indent=2, default=str)

    # ── step API ──────────────────────────────────────────────────────────────

    def is_done(self, step: str) -> bool:
        s = self._data.steps.get(step)
        return s is not None and s.status == "done"

    def mark_done(self, step: str, meta: dict | None = None) -> None:
        merged_meta = meta or {}
        existing = self._data.steps.get(step)
        if existing is not None and "substeps" in existing.meta and "substeps" not in merged_meta:
            merged_meta = {**merged_meta, "substeps": existing.meta["substeps"]}
        self._data.steps[step] = StepState(
            status="done",
            completed_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            meta=merged_meta,
        )
        self.save()

    def mark_substep_done(self, step: str, substep: str, meta: dict | None = None) -> None:
        parent = self._data.steps.get(step)
        parent_meta = dict(parent.meta) if parent is not None else {}
        substeps = dict(parent_meta.get("substeps", {}))
        substeps[substep] = {
            "status": "done",
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            **(meta or {}),
        }
        parent_meta["substeps"] = substeps
        parent_status = parent.status if parent is not None else "pending"
        self._data.steps[step] = StepState(
            status=parent_status,
            completed_at=parent.completed_at if parent is not None else None,
            reason=parent.reason if parent is not None else None,
            meta=parent_meta,
        )
        self.save()

    def mark_skipped(self, step: str, reason: str = "") -> None:
        self._data.steps[step] = StepState(status="skipped", reason=reason)
        self.save()

    def mark_substep_skipped(self, step: str, substep: str, reason: str = "") -> None:
        parent = self._data.steps.get(step)
        parent_meta = dict(parent.meta) if parent is not None else {}
        substeps = dict(parent_meta.get("substeps", {}))
        substeps[substep] = {"status": "skipped", "reason": reason}
        parent_meta["substeps"] = substeps
        self._data.steps[step] = StepState(
            status=parent.status if parent is not None else "pending",
            completed_at=parent.completed_at if parent is not None else None,
            reason=parent.reason if parent is not None else None,
            meta=parent_meta,
        )
        self.save()

    def get(self, step: str) -> dict:
        s = self._data.steps.get(step)
        return s.to_dict() if s is not None else {}

    def get_substep(self, step: str, substep: str) -> dict:
        parent = self.get(step)
        substeps = parent.get("substeps") if isinstance(parent.get("substeps"), dict) else {}
        data = substeps.get(substep)
        if isinstance(data, dict):
            return data
        if parent.get("status") == "done":
            return {"status": "done", "legacy_parent_done": True}
        if parent.get("status") == "skipped":
            return {"status": "skipped", "reason": parent.get("reason", "")}
        return {}

    def reset(self, step: str | None = None) -> None:
        if step:
            self._data.steps.pop(step, None)
        else:
            self._data.steps = {}
        self.save()

    def reset_steps(self, steps: Iterable[str]) -> None:
        """Remove several step records while persisting the manifest once."""

        for step in set(steps):
            self._data.steps.pop(step, None)
        self.save()
