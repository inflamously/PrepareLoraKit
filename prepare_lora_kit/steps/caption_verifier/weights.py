"""How much of a checkpoint's weights have landed, in bytes.

The elapsed counter in :mod:`.load_status` proves a load is alive; it cannot say
how far through it is. This module answers that in the only unit that means
anything to someone waiting: the weight bytes themselves.

**The denominator is exact.** It is the size of the weight files this load will
read, measured on disk in the Hugging Face cache — not a parameter-count
estimate like the ``params_b`` figures in :mod:`.catalog`.

**The numerator is component-granular**, because that is all diffusers exposes.
Two tqdm bars carry it:

* ``Loading pipeline components...`` counts *components* (``vae``,
  ``text_encoder``, ``transformer``, …) as each finishes. Sizes differ by an
  order of magnitude between them, so counting them is useless on its own —
  this module converts each completed one into its real byte size instead.
* ``Loading checkpoint shards`` moves *within* a component, and only for the
  multi-shard ones. That is exactly where the wait is on a 9B: it refines the
  transformer and the text encoder, and single-file components (a VAE) never
  need it because they complete in one step of the bar above.

So the reading is precise to a shard inside the big components and to a
component elsewhere. It never runs backwards: the figure is high-watermarked,
because a progress line that retreats reads as a fault rather than as the
re-scan it actually is.

Nothing here imports torch, diffusers or huggingface_hub at module scope —
``tests/steps/test_imports.py`` imports every module under ``steps/``.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

# .bin is the pre-safetensors format; a repo carrying both ships the same
# weights twice, which is why _component_size never sums across the two.
_WEIGHT_SUFFIXES = (".safetensors", ".bin")
_PIPELINE_INDEX = "model_index.json"

# Substrings of the tqdm descriptions this tracker understands. Matched loosely
# because they are Hugging Face's wording, not an API: a release that retitles
# "Loading checkpoint shards" costs the shard refinement, never the load.
_COMPONENT_BAR = "pipeline components"
_SHARD_BARS = ("checkpoint shards", "state_dict")


@dataclass(frozen=True)
class WeightComponent:
    """One pipeline component and the bytes of weights it loads."""

    name: str
    size: int


def read_components(
    model_id: str, *, skip: Iterable[str] = (),
) -> tuple[WeightComponent, ...] | None:
    """The components of ``model_id``, in load order, or ``None``.

    ``None`` whenever the checkpoint cannot be measured — a single-file model id,
    a repo that is still downloading, an unreadable cache. The caller then shows
    no weight figure at all, which is the honest answer; a total invented from
    parameter counts would be wrong by whatever the quantization and the file
    format decided.

    ``skip`` names components the loader passes as ``None`` (SD 1.5's
    ``safety_checker``). They are absent from diffusers' ``init_dict``, so
    counting them would both inflate the total and offset every position in it.
    """
    root = _snapshot_dir(model_id)
    if root is None:
        return None
    try:
        index = json.loads((root / _PIPELINE_INDEX).read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(index, dict):
        return None

    skipped = {str(name) for name in skip}
    components = tuple(
        WeightComponent(name, _component_size(root / name))
        # Insertion order is load order: diffusers builds init_dict from this
        # file and iterates it, and both dicts keep the JSON's ordering.
        for name in index
        if not name.startswith("_") and name not in skipped
    )
    if not any(component.size for component in components):
        return None
    return components


class WeightProgress:
    """Weight bytes loaded so far, fed by the load's own tqdm bars.

    Lives across the whole load and is written from whichever thread drives a
    bar — diffusers loads shards on a thread pool — while the heartbeat samples
    it from another, hence the lock.
    """

    def __init__(self, model_id: str, *, skip: Iterable[str] = ()) -> None:
        self._model_id = model_id
        self._skip = tuple(skip)
        self._lock = threading.Lock()
        self._components: tuple[WeightComponent, ...] | None = None
        self._done = 0  # components the pipeline bar has finished
        self._counted = 0  # what that bar counts, which need not be our count
        self._shard = 0.0  # how far into the component in flight
        self._loaded = 0  # high-watermark, so the figure never retreats

    def note(self, bar: Any) -> None:
        """Record a tqdm bar. Runs on whichever thread drives it."""
        description = str(getattr(bar, "desc", "") or "").lower()
        current = _count(getattr(bar, "n", None))
        total = _count(getattr(bar, "total", None))

        if _COMPONENT_BAR in description:
            with self._lock:
                if current != self._done:
                    # A new component is in flight; the old one's shard bar has
                    # closed and its fraction now belongs to nothing.
                    self._shard = 0.0
                self._done, self._counted = current, total
            return

        if total and any(name in description for name in _SHARD_BARS):
            with self._lock:
                self._shard = min(1.0, max(0.0, current / total))

    def snapshot(self) -> tuple[int, int] | None:
        """``(loaded_bytes, total_bytes)``, or ``None`` while unmeasurable."""
        components = self._resolve()
        if components is None:
            return None
        total = sum(component.size for component in components)
        if total <= 0:  # pragma: no cover - read_components rejects these
            return None

        with self._lock:
            position = _position(self._done, self._counted, len(components))
            loaded = sum(component.size for component in components[:position])
            if position < len(components):
                loaded += int(self._shard * components[position].size)
            self._loaded = min(total, max(loaded, self._loaded))
            return self._loaded, total

    def _resolve(self) -> tuple[WeightComponent, ...] | None:
        """Read the checkpoint once it is on disk.

        Retried on every sample rather than cached as a failure: on a first run
        the files do not exist yet when the load starts, and they appear part
        way through — exactly when this becomes worth showing.
        """
        if self._components is not None:
            return self._components
        try:
            self._components = read_components(self._model_id, skip=self._skip)
        except Exception:  # pragma: no cover - best effort
            return None
        return self._components


# --- internals -------------------------------------------------------------

def _snapshot_dir(model_id: str) -> Path | None:
    """The local folder holding ``model_id``'s files, or ``None``.

    Cache only — never a download, and never a Hub request. This runs on the
    heartbeat while the UI waits on the load, where a network round trip would
    buy a status line at the cost of the thing it describes.
    """
    identifier = str(model_id or "").strip()
    if not identifier or "::" in identifier:
        return None  # a single file inside a repo: no pipeline to measure

    local = Path(identifier)
    if local.is_dir():
        return local if (local / _PIPELINE_INDEX).is_file() else None
    if local.suffix.lower() in (".safetensors", ".ckpt", ".pt", ".bin"):
        return None

    try:
        from huggingface_hub import try_to_load_from_cache

        cached = try_to_load_from_cache(identifier, _PIPELINE_INDEX)
    except Exception:  # pragma: no cover - best effort
        return None
    return Path(cached).parent if isinstance(cached, str) else None


def _component_size(folder: Path) -> int:
    """Bytes of the weight files in one component folder.

    Counts each set of weights once. A repo may ship ``.safetensors`` beside
    legacy ``.bin``, and fp16/bf16 variants beside the plain files; the load
    reads one of each, so summing the folder would double or triple the total.
    """
    try:
        files = [path for path in folder.iterdir() if path.is_file()]
    except OSError:
        return 0

    for suffix in _WEIGHT_SUFFIXES:
        matching = [path for path in files if path.suffix == suffix]
        if matching:
            break
    else:
        return 0

    chosen: dict[str, Path] = {}
    for path in sorted(matching):
        # "model-00001-of-00002.fp16.safetensors" -> shard key, variant "fp16".
        key, _, variant = path.name[: -len(path.suffix)].partition(".")
        if key not in chosen or not variant:
            chosen[key] = path
    return sum(_size(path) for path in chosen.values())


def _position(done: int, counted: int, available: int) -> int:
    """Which component is in flight, given a bar that may count differently.

    ``counted`` is what diffusers' component bar totals. It should equal our
    list, and does whenever ``skip`` is right — but a diffusers release that
    hands ``init_dict`` one more or one fewer entry must not silently credit the
    wrong component's bytes, so the position is scaled rather than trusted.
    """
    if counted <= 0 or counted == available:
        return min(max(done, 0), available)
    return min(available, max(0, int(done * available / counted)))


def _size(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:  # pragma: no cover - best effort
        return 0


def _count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value)
