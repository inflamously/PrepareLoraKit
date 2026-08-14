"""The generator closure the UI's bridge RPC lands on.

Preview PNGs are written outside ``dataset/`` on purpose: ``iter_images`` recurses, so a
probe image inside the working dataset would be picked up as training data.
"""
from __future__ import annotations

import secrets
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from prepare_lora_kit.cancellation import CancelCheck, check_cancel
from prepare_lora_kit.steps.caption_verifier.loader import preview_dir_for
from prepare_lora_kit.steps.caption_verifier.t2i import T2IRuntime

_MAX_PREVIEWS_PER_IMAGE = 8


def make_caption_generator(
    *,
    runtime: T2IRuntime,
    preview_root: Path,
    generations: dict[str, list[dict]],
    failures: list[dict],
    base_seed: int = 42,
    cancel_check: CancelCheck | None = None,
) -> Callable[[str, dict], dict]:
    """Build the ``(prompt, options) -> dict`` callable handed to the provider.

    ``generations`` and ``failures`` are the step's own accumulators, mutated in
    place so the report reflects everything the user actually rendered.
    """
    preview_root = Path(preview_root)

    def generate(prompt: str, options: dict[str, Any] | None = None) -> dict:
        opts = dict(options or {})
        check_cancel(cancel_check)

        source = Path(str(opts.get("source_path") or ""))
        if not str(source):
            raise ValueError("source_path is required to generate a preview.")

        key = str(source)
        previous = generations.setdefault(key, [])
        seed = _next_seed(opts, previous, source, base_seed)

        try:
            result = runtime.generate(
                prompt,
                seed=seed,
                width=_optional_int(opts.get("width")),
                height=_optional_int(opts.get("height")),
                steps=_optional_int(opts.get("steps")),
                guidance=_optional_float(opts.get("guidance")),
                cancel_check=(lambda: check_cancel(cancel_check)) if cancel_check else None,
            )
        except Exception as exc:
            # Recorded for the report, then re-raised so the provider turns it
            # into a rejected promise the modal shows inline. The pipeline
            # thread is parked in request_input on a *different* thread, so
            # raising here never kills the run.
            failures.append({
                "stage": "generate",
                "path": key,
                "error": f"{type(exc).__name__}: {exc}",
            })
            raise

        target = _preview_path(preview_root, source, result.seed, len(previous))
        target.parent.mkdir(parents=True, exist_ok=True)
        result.image.save(target, format="PNG")

        record = {**result.as_dict(), "path": str(target), "prompt": result.prompt}
        previous.append(record)
        _prune(previous, key, generations)
        return record

    return generate


def _preview_path(root: Path, source: Path, seed: int, index: int) -> Path:
    """A fresh filename per render.

    The UI media endpoint sends ``Cache-Control: private, max-age=86400``, so a
    re-roll written over the same path would be served from the browser cache
    without revalidation and silently show the previous image.
    """
    return preview_dir_for(root, source) / f"gen_{seed}_{index:03d}.png"


def _next_seed(
    opts: dict, previous: list[dict], source: Path, base_seed: int,
) -> int:
    explicit = opts.get("seed")
    if explicit is not None:
        return int(explicit) % (2 ** 32)
    if opts.get("reroll"):
        return secrets.randbelow(2 ** 31)
    if previous:
        return int(previous[-1].get("seed", base_seed))
    # Deterministic first render per image, so re-opening the modal reproduces
    # what the user saw last time.
    return (int(base_seed) + zlib.crc32(str(source).encode("utf-8"))) % (2 ** 31)


def _prune(previous: list[dict], key: str, generations: dict[str, list[dict]]) -> None:
    """Bound disk growth from repeated re-rolls, oldest first."""
    while len(previous) > _MAX_PREVIEWS_PER_IMAGE:
        stale = previous.pop(0)
        path = stale.get("path")
        if path:
            Path(path).unlink(missing_ok=True)
    generations[key] = previous


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
