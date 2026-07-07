"""Console output helpers for BucketPoolsCheckStep."""
from __future__ import annotations

from rich import box
from rich.table import Table

from prepare_lora_kit.cancellation import CancelCheck, check_cancel
from prepare_lora_kit.report import reporter


def print_bucket_table(
    bucket_map: dict[tuple[int, int], list[str]],
    *,
    display_name: str,
    thin_buckets: list[dict],
    cancel_check: CancelCheck | None = None,
) -> None:
    t = Table(title=f"Bucket Assignment — {display_name}", box=box.SIMPLE_HEAVY)
    t.add_column("Bucket", style="cyan", width=14)
    t.add_column("Count", justify="right", width=7)
    t.add_column("Status", width=10)
    t.add_column("Suggestion", style="dim")

    thin_by_bucket = {
        tuple(thin_bucket["bucket"]): thin_bucket
        for thin_bucket in thin_buckets
    }

    for bucket, paths in sorted(bucket_map.items()):
        check_cancel(cancel_check)
        n = len(paths)
        if n == 0:
            continue

        thin_bucket = thin_by_bucket.get(bucket)
        if thin_bucket:
            status = "[yellow]THIN[/yellow]"
            suggestion = thin_bucket["suggestion"]
        else:
            status = "[green]OK[/green]"
            suggestion = ""
        t.add_row(f"{bucket[0]}×{bucket[1]}", str(n), status, suggestion)

    reporter.console.print(t)


def print_thin_bucket_summary(
    thin_buckets: list[dict],
    *,
    thin_threshold: int,
    cancel_check: CancelCheck | None = None,
) -> None:
    if thin_buckets:
        reporter.warn(f"{len(thin_buckets)} thin bucket(s) (≤ {thin_threshold} images):")
        for thin_bucket in thin_buckets:
            check_cancel(cancel_check)
            bucket = thin_bucket["bucket"]
            reporter.warn(
                f"  {bucket[0]}×{bucket[1]}: "
                f"{thin_bucket['count']} image(s) — {thin_bucket['suggestion']}"
            )
        reporter.info(
            "Fix options: crop images to a more common aspect ratio, "
            "or increase `repeats` for that folder."
        )
    else:
        reporter.ok("No thin buckets detected.")
