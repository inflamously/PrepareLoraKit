"""Perceptual-hash dedupe for CurateStep."""
from __future__ import annotations

from pathlib import Path

from prepare_lora_kit.cancellation import CancelCheck, cancellable, noop_cancel_check
from prepare_lora_kit.report import reporter

HASH_DISTANCE = 8


def _compute_hashes(
    paths: list[Path], cancel_check: CancelCheck = noop_cancel_check,
) -> dict[Path, object]:
    import imagehash
    from PIL import Image
    hashes = {}
    for p in cancellable(paths, cancel_check):
        try:
            hashes[p] = imagehash.phash(Image.open(p).convert("RGB"))
        except Exception as exc:
            reporter.warn(f"Hash failed for {p.name}: {exc}")
    return hashes


def _find_duplicates(
    hashes: dict[Path, object],
    max_distance: int = HASH_DISTANCE,
    cancel_check: CancelCheck = noop_cancel_check,
) -> list[tuple[Path, Path, int]]:
    """Return list of (path_a, path_b, hamming_distance) for near-duplicate pairs.

    Pairs whose perceptual-hash Hamming distance is ``<= max_distance`` are flagged.
    Lower ``max_distance`` = stricter (only near-identical images flagged).
    """
    items = list(hashes.items())
    dupes = []
    for i in cancellable(range(len(items)), cancel_check):
        for j in range(i + 1, len(items)):
            dist = items[i][1] - items[j][1]
            if dist <= max_distance:
                dupes.append((items[i][0], items[j][0], dist))
    return dupes


def _resolve_duplicates(
    pairs: list[tuple[Path, Path, int]],
    auto_drop: bool = True,
    cancel_check: CancelCheck = noop_cancel_check,
) -> set[Path]:
    """Return set of paths to drop. Auto-drops the blurrier of each pair."""
    from prepare_lora_kit.utils.image import blur_score
    to_drop: set[Path] = set()
    for a, b, dist in cancellable(pairs, cancel_check):
        if a in to_drop or b in to_drop:
            continue
        blur_a = blur_score(a)
        blur_b = blur_score(b)
        drop = a if blur_a <= blur_b else b
        keep = b if drop is a else a
        if auto_drop:
            to_drop.add(drop)
            reporter.warn(f"DEDUPE drop {drop.name} (blur={blur_a if drop == a else blur_b:.1f}) "
                     f"← dupe of {keep.name} (dist={dist})")
        else:
            # easygui tie-break
            try:
                import easygui
                choice = easygui.buttonbox(
                    f"Near-duplicate pair (Hamming={dist}):\n\nA: {a.name}  (blur={blur_a:.1f})\n"
                    f"B: {b.name}  (blur={blur_b:.1f})\n\nWhich to DROP?",
                    title="Curate — Dedupe",
                    choices=[f"Drop {a.name}", f"Drop {b.name}", "Keep both"],
                )
                if choice and "Drop " in choice:
                    dropped = a if a.name in choice else b
                    to_drop.add(dropped)
            except ImportError:
                to_drop.add(drop)
    return to_drop
