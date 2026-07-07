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
from pathlib import Path

from PIL import Image

from ...cancellation import CancelCheck, check_cancel
from ...utils import image as img_utils
from prepare_lora_kit.report import reporter
from rich.table import Table
from rich import box

from .bucketing import _find_bucket, _suggest_crop

THIN_BUCKET_THRESHOLD = 2


def run(
    dataset_dir: Path,
    resolution_buckets: list[tuple[int, int]],
    display_name: str = "configured bucket pools",
    output_dir: Path | None = None,
    cache_mode: bool = False,
    thin_threshold: int = THIN_BUCKET_THRESHOLD,
    report_path: Path | None = None,
    enabled_substeps: list[str] | None = None,
    cancel_check: CancelCheck | None = None,
) -> dict:
    reporter.step_header("Bucket Dry-run")
    enabled = set(enabled_substeps or ["assign_bucket_pools", "report_thin_buckets"])

    output_dir = output_dir or dataset_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    images = img_utils.iter_images(dataset_dir)
    if not images:
        reporter.warn(f"No images in {dataset_dir}")
        return {}

    if "assign_bucket_pools" not in enabled:
        report_data = {
            "skipped": True,
            "reason": "assign_bucket_pools disabled",
            "buckets": {},
            "thin_buckets": [],
            "cache_mode": False,
            "substeps": {
                "assign_bucket_pools": {"enabled": False},
                "report_thin_buckets": {"enabled": "report_thin_buckets" in enabled},
                "write_cache_info": {"enabled": "write_cache_info" in enabled},
            },
        }
        reporter.save_report(report_data, report_path or (output_dir / "step8_report.json"))
        return report_data

    buckets = [tuple(bucket) for bucket in resolution_buckets]
    bucket_map: dict[tuple[int, int], list[str]] = {b: [] for b in buckets}

    for path in images:
        check_cancel(cancel_check)
        try:
            with Image.open(path) as img:
                iw, ih = img.size
        except Exception as exc:
            reporter.warn(f"Could not read {path.name}: {exc}")
            continue
        best = _find_bucket(iw, ih, buckets)
        bucket_map[best].append(str(path))

    # ── Print bucket table ────────────────────────────────────────────────────
    t = Table(title=f"Bucket Assignment — {display_name}", box=box.SIMPLE_HEAVY)
    t.add_column("Bucket", style="cyan", width=14)
    t.add_column("Count", justify="right", width=7)
    t.add_column("Status", width=10)
    t.add_column("Suggestion", style="dim")

    thin_buckets: list[dict] = []
    for bkt, paths in sorted(bucket_map.items()):
        check_cancel(cancel_check)
        n = len(paths)
        if n == 0:
            continue
        if "report_thin_buckets" in enabled and n <= thin_threshold:
            status = "[yellow]THIN[/yellow]"
            # Suggest crop for the images that ended up here
            suggestions = []
            for p in paths:
                check_cancel(cancel_check)
                with Image.open(p) as img:
                    iw, ih = img.size
                suggestions.append(_suggest_crop(iw, ih, bkt[0], bkt[1]))
            suggestion = "; ".join(dict.fromkeys(suggestions))
            thin_buckets.append({"bucket": list(bkt), "count": n, "paths": paths, "suggestion": suggestion})
        else:
            status = "[green]OK[/green]"
            suggestion = ""
        t.add_row(f"{bkt[0]}×{bkt[1]}", str(n), status, suggestion)

    reporter.console.print(t)

    if thin_buckets:
        reporter.warn(f"{len(thin_buckets)} thin bucket(s) (≤ {thin_threshold} images):")
        for tb in thin_buckets:
            check_cancel(cancel_check)
            bkt = tb["bucket"]
            reporter.warn(f"  {bkt[0]}×{bkt[1]}: {tb['count']} image(s) — {tb['suggestion']}")
        reporter.info("Fix options: crop images to a more common aspect ratio, or increase `repeats` for that folder.")
    else:
        reporter.ok("No thin buckets detected.")

    # ── Cache mode ────────────────────────────────────────────────────────────
    cache_info: dict | None = None
    if cache_mode and "write_cache_info" in enabled:
        cache_info = {
            "bucket_source": display_name,
            "buckets": {
                f"{bw}x{bh}": paths
                for (bw, bh), paths in bucket_map.items()
                if paths
            },
        }
        cache_path = output_dir / "cache_info.json"
        check_cancel(cancel_check)
        with open(cache_path, "w") as f:
            json.dump(cache_info, f, indent=2)
        reporter.ok(f"Cache info written → {cache_path}")

    report_data = {
        "buckets": {
            f"{bw}x{bh}": {"count": len(paths), "paths": paths}
            for (bw, bh), paths in bucket_map.items()
        },
        "thin_buckets": thin_buckets,
        "cache_mode": cache_mode and "write_cache_info" in enabled,
        "substeps": {
            "assign_bucket_pools": {"enabled": "assign_bucket_pools" in enabled},
            "report_thin_buckets": {"enabled": "report_thin_buckets" in enabled},
            "write_cache_info": {"enabled": "write_cache_info" in enabled},
        },
    }
    check_cancel(cancel_check)
    reporter.save_report(report_data, report_path or (output_dir / "step8_report.json"))
    return report_data
