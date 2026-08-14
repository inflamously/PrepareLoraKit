"""Deterministic mock runtime for CaptionVerifierStep (``--mock``): a PIL render stands in
for the diffusion model, everything else is the real code path.
"""
from __future__ import annotations

import time
import zlib
from pathlib import Path

from prepare_lora_kit.cancellation import check_cancel

# Long enough to exercise the modal's busy-lock and spinner, short enough that
# clicking through a gallery stays pleasant.
_FAKE_RENDER_SECONDS = 0.6


def _make_mock_generator(preview_root: Path, generations: dict, cancel_check):
    """Build the render callback the modal calls, faking a diffusion pass.

    Records exactly the same shape the real T2I runtime returns, and appends to
    ``generations`` so re-rolls accumulate per source image the way they do in a
    real run.
    """
    from prepare_lora_kit.steps.caption_verifier.loader import preview_dir_for

    def _generator(prompt: str, options: dict | None = None) -> dict:
        check_cancel(cancel_check)
        opts = dict(options or {})
        source = Path(str(opts.get("source_path") or ""))
        seed = _seed_for(opts, generations.get(str(source), []))
        image = _plate(prompt, seed)
        time.sleep(_FAKE_RENDER_SECONDS)

        entries = generations.setdefault(str(source), [])
        target = preview_dir_for(preview_root, source) / f"gen_{seed}_{len(entries):03d}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, format="PNG")
        record = {
            "seed": seed, "width": image.width, "height": image.height,
            "steps": 4, "guidance": 1.0, "elapsed_ms": int(_FAKE_RENDER_SECONDS * 1000),
            "model_id": "mock", "truncated": False, "token_count": len(prompt.split()),
            "path": str(target), "prompt": prompt,
        }
        entries.append(record)
        return record

    return _generator


def _mock_caption_verifier(
        working_dir: Path,
        output_dir: Path,
        *,
        interaction=None,
        enabled_substeps: list[str] | None = None,
        cancel_check=None,
) -> dict:
    from prepare_lora_kit.project.pipeline.substeps import substep_ids_for
    from prepare_lora_kit.report import reporter, step_report_path
    from prepare_lora_kit.steps.caption_verifier import captions as caption_io
    from prepare_lora_kit.steps.caption_verifier import reports, verdicts
    from prepare_lora_kit.steps.caption_verifier.step import (
        BACKUP_DIR_NAME,
        PREVIEW_DIR_NAME,
        STEP_TYPE,
    )
    from prepare_lora_kit.utils.verdict_ledger import VerdictLedger

    reporter.step_header("Caption Verifier — Text-Encoder Probe (mock)")
    enabled = set(enabled_substeps or substep_ids_for(STEP_TYPE))
    report_path = step_report_path(output_dir, "CaptionVerifierStep")
    preview_root = report_path.parent / PREVIEW_DIR_NAME

    items = caption_io.collect_verifiable_images(working_dir)
    verdicts.seed_initial_verdicts(items, VerdictLedger(report_path.parent))
    generations: dict[str, list[dict]] = {}
    failures: list[dict] = []

    _generator = _make_mock_generator(preview_root, generations, cancel_check)

    verify = getattr(interaction, "caption_verify", None) if interaction else None
    results: dict[str, dict] = {}
    reason: str | None = None
    if "verify_captions" not in enabled:
        reason = "verify_captions substep disabled"
    elif not items:
        reason = "no captioned images"
    elif verify is None:
        reason = "no interactive caption verification provider"
    else:
        check_cancel(cancel_check)
        results = verify(
            items,
            generator=_generator,
            preview_dir=preview_root,
            settings={"model_id": "mock", "steps": 4, "guidance": 1.0,
                      "verdicts": list(reports.VERDICTS)},
        ) or {}

    check_cancel(cancel_check)
    applied: list[dict] = []
    rejected: list[dict] = []
    if results and "apply_caption_edits" in enabled:
        edits = {
            path: entry.get("caption", "")
            for path, entry in results.items()
            if isinstance(entry, dict) and entry.get("caption") is not None
        }
        applied, rejected = caption_io.apply_caption_edits(
            working_dir, edits, backup_dir=preview_root / BACKUP_DIR_NAME,
        )

    # Same ledger write as the real step, so --mock exercises the whole
    # verify → reopen-in-CaptionBbox loop on a machine with no GPU.
    if results:
        ledger = VerdictLedger(report_path.parent)
        verdicts.record_results(
            ledger, items=items, results=results, applied=applied,
        )
        ledger.save()

    report_data = reports.build_report(
        items=items,
        results=results,
        generations=generations,
        applied=applied,
        rejected=rejected,
        failures=failures,
        model={"model_id": "mock", "family": "mock", "loaded": True},
        status={"phase": "ready", "message": "mock runtime"},
        defaults={"steps": 4, "guidance": 1.0, "seed": 42},
        enabled_substeps=enabled,
        reason=reason,
    )
    report_data["mock_runtime"] = True
    reporter.info(
        f"Mock runtime: verified {len(items)} caption(s), "
        f"{sum(len(v) for v in generations.values())} render(s)."
    )
    check_cancel(cancel_check)
    reporter.save_report(report_data, report_path)
    return report_data


def _seed_for(opts: dict, previous: list[dict]) -> int:
    explicit = opts.get("seed")
    if explicit is not None:
        return int(explicit) % (2 ** 32)
    if opts.get("reroll"):
        # Derived from the render count rather than randomness so the mock
        # stays reproducible across processes while still visibly changing.
        return (len(previous) + 1) * 7919
    if previous:
        return int(previous[-1].get("seed", 0))
    return 42


def _plate(prompt: str, seed: int):
    """A deterministic colour plate keyed on (prompt, seed).

    ``zlib.crc32`` rather than the builtin ``hash``: str hashing is
    PYTHONHASHSEED-salted, which would break determinism across processes.
    """
    from PIL import Image, ImageDraw

    digest = zlib.crc32(f"{prompt}|{seed}".encode())
    base = ((digest >> 16) & 0xFF, (digest >> 8) & 0xFF, digest & 0xFF)
    image = Image.new("RGB", (384, 384), base)
    draw = ImageDraw.Draw(image)
    for index in range(6):
        shade = zlib.crc32(f"{prompt}|{seed}|{index}".encode())
        draw.rectangle(
            [24, 40 + index * 52, 360, 80 + index * 52],
            fill=((shade >> 16) & 0xFF, (shade >> 8) & 0xFF, shade & 0xFF),
        )
    draw.text((16, 12), f"mock seed {seed}", fill=(255, 255, 255))
    draw.text((16, 350), prompt[:48], fill=(255, 255, 255))
    return image
