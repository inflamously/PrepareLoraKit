"""Benchmark run records and their JSON files under ``<suite>/runs/``."""
from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from prepare_lora_kit.paths import PROJECT_ROOT

_TIMESTAMP = "%Y%m%d-%H%M%S"


@dataclass
class CaseResult:
    """What one variant produced for one image."""

    image: str
    caption: str
    raw_caption: str = ""
    trace: dict[str, Any] = field(default_factory=dict)
    passes: dict[str, int] = field(default_factory=dict)
    seconds: float = 0.0
    words: int = 0
    error: str | None = None


@dataclass
class BenchRun:
    """One variant captioning a whole suite."""

    run_id: str
    variant: str
    suite: str
    created_at: str
    git_commit: str | None
    model: dict[str, Any]
    config: dict[str, Any]
    results: list[CaseResult] = field(default_factory=list)

    def result_for(self, image: str) -> CaseResult | None:
        return next((r for r in self.results if r.image == image), None)

    @property
    def total_seconds(self) -> float:
        return sum(r.seconds for r in self.results)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchRun:
        results = [CaseResult(**r) for r in data.get("results", [])]
        return cls(**{**data, "results": results})


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def parse_timestamp(text: str) -> datetime:
    """Inverse of the run-id timestamp, for tests and sorting."""
    return datetime.strptime(text, _TIMESTAMP).replace(tzinfo=timezone.utc)


def make_run_id(created: datetime, variant: str) -> str:
    return f"{created.strftime(_TIMESTAMP)}__{variant}"


def git_commit() -> str | None:
    """Short HEAD commit of the checkout, ``+dirty`` when uncommitted changes exist.

    Recorded so a run can be traced back to the code that produced it; ``None``
    when git is unavailable (e.g. an installed wheel).
    """
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT,
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"], cwd=PROJECT_ROOT,
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return f"{head}+dirty" if dirty else head


def save_run(suite_root: Path, run: BenchRun) -> Path:
    runs_dir = Path(suite_root) / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"{run.run_id}.json"
    # Two runs of one variant within the same second must not overwrite each other.
    n = 2
    while path.exists():
        run.run_id = f"{run.run_id.rsplit('#', 1)[0]}#{n}"
        path = runs_dir / f"{run.run_id}.json"
        n += 1
    path.write_text(json.dumps(asdict(run), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_run(path: Path) -> BenchRun:
    return BenchRun.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def list_runs(suite_root: Path) -> list[BenchRun]:
    """Every stored run, oldest first (run ids start with a sortable timestamp)."""
    runs_dir = Path(suite_root) / "runs"
    if not runs_dir.is_dir():
        return []
    return [load_run(path) for path in sorted(runs_dir.glob("*.json"))]


def find_run(suite_root: Path, ref: str) -> BenchRun:
    """Resolve a run id, or a unique prefix of one."""
    runs = list_runs(suite_root)
    exact = [run for run in runs if run.run_id == ref]
    matches = exact or [run for run in runs if run.run_id.startswith(ref)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"No benchmark run matches '{ref}'")
    raise ValueError(
        f"'{ref}' is ambiguous: {', '.join(run.run_id for run in matches)}"
    )
