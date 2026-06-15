"""
Step 8 — Bucket Dry-run

Simulates ai-toolkit's multi-resolution bucketing without actually training.
Assigns each image to its closest bucket by aspect-ratio distance, then flags
thin buckets (≤ 2 images) and suggests fixes (crop or repeats).

Optional --cache-mode: writes a cache_info.json compatible with ai-toolkit's
cache_latents_to_disk path structure for re-use on the real run.
"""
from __future__ import annotations
import json
import math
from pathlib import Path

from PIL import Image

from ..networks.base import NetworkProfile
from ..utils import image as img_utils
from ..utils import report as rpt
from rich.table import Table
from rich import box

THIN_BUCKET_THRESHOLD = 2


def _aspect(w: int, h: int) -> float:
    return w / h


def _bucket_distance(img_w: int, img_h: int, bw: int, bh: int) -> float:
    img_ar = _aspect(img_w, img_h)
    bkt_ar = _aspect(bw, bh)
    return abs(math.log(img_ar) - math.log(bkt_ar))


def _find_bucket(img_w: int, img_h: int, buckets: list[tuple[int, int]]) -> tuple[int, int]:
    return min(buckets, key=lambda b: _bucket_distance(img_w, img_h, b[0], b[1]))


def _suggest_crop(img_w: int, img_h: int, bw: int, bh: int) -> str:
    target_ar = bw / bh
    if img_w / img_h > target_ar:
        new_w = int(img_h * target_ar)
        return f"centre-crop width to {new_w}px (from {img_w}px)"
    else:
        new_h = int(img_w / target_ar)
        return f"centre-crop height to {new_h}px (from {img_h}px)"


def run(
    dataset_dir: Path,
    network: NetworkProfile,
    output_dir: Path | None = None,
    cache_mode: bool = False,
    thin_threshold: int = THIN_BUCKET_THRESHOLD,
) -> dict:
    rpt.step_header(8, "Bucket Dry-run")

    output_dir = output_dir or dataset_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    images = img_utils.iter_images(dataset_dir)
    if not images:
        rpt.warn(f"No images in {dataset_dir}")
        return {}

    buckets = network.resolution_buckets
    bucket_map: dict[tuple[int, int], list[str]] = {b: [] for b in buckets}

    for path in images:
        try:
            with Image.open(path) as img:
                iw, ih = img.size
        except Exception as exc:
            rpt.warn(f"Could not read {path.name}: {exc}")
            continue
        best = _find_bucket(iw, ih, buckets)
        bucket_map[best].append(str(path))

    # ── Print bucket table ────────────────────────────────────────────────────
    t = Table(title=f"Bucket Assignment — {network.display_name}", box=box.SIMPLE_HEAVY)
    t.add_column("Bucket", style="cyan", width=14)
    t.add_column("Count", justify="right", width=7)
    t.add_column("Status", width=10)
    t.add_column("Suggestion", style="dim")

    thin_buckets: list[dict] = []
    for bkt, paths in sorted(bucket_map.items()):
        n = len(paths)
        if n == 0:
            continue
        if n <= thin_threshold:
            status = "[yellow]THIN[/yellow]"
            # Suggest crop for the images that ended up here
            suggestions = []
            for p in paths:
                with Image.open(p) as img:
                    iw, ih = img.size
                suggestions.append(_suggest_crop(iw, ih, bkt[0], bkt[1]))
            suggestion = "; ".join(dict.fromkeys(suggestions))
            thin_buckets.append({"bucket": list(bkt), "count": n, "paths": paths, "suggestion": suggestion})
        else:
            status = "[green]OK[/green]"
            suggestion = ""
        t.add_row(f"{bkt[0]}×{bkt[1]}", str(n), status, suggestion)

    from ..utils.report import console
    console.print(t)

    if thin_buckets:
        rpt.warn(f"{len(thin_buckets)} thin bucket(s) (≤ {thin_threshold} images):")
        for tb in thin_buckets:
            bkt = tb["bucket"]
            rpt.warn(f"  {bkt[0]}×{bkt[1]}: {tb['count']} image(s) — {tb['suggestion']}")
        rpt.info("Fix options: crop images to a more common aspect ratio, or increase `repeats` for that folder.")
    else:
        rpt.ok("No thin buckets detected.")

    # ── Cache mode ────────────────────────────────────────────────────────────
    cache_info: dict | None = None
    if cache_mode:
        cache_info = {
            "network": network.name,
            "buckets": {
                f"{bw}x{bh}": paths
                for (bw, bh), paths in bucket_map.items()
                if paths
            },
        }
        cache_path = output_dir / "cache_info.json"
        with open(cache_path, "w") as f:
            json.dump(cache_info, f, indent=2)
        rpt.ok(f"Cache info written → {cache_path}")

    report = {
        "buckets": {
            f"{bw}x{bh}": {"count": len(paths), "paths": paths}
            for (bw, bh), paths in bucket_map.items()
        },
        "thin_buckets": thin_buckets,
        "cache_mode": cache_mode,
    }
    rpt.save_report(report, output_dir / "step8_report.json")
    return report
