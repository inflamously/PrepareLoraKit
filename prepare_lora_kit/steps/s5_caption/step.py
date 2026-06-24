"""
Step 5 — Caption with Bbox Annotation + Qwen3-VL BFL-structured captioning

For each image:
  1. Open a tkinter bbox-draw canvas (Ideogram-4-style region annotation).
  2. User draws boxes and labels each region.
  3. Bbox context + image are sent to Qwen3-VL to produce a BFL-structured caption.
  4. Caption is cleaned, token-checked, and saved as {stem}.txt.
"""
from __future__ import annotations
import random
from pathlib import Path

from ...cancellation import CancelCheck, CancelledRun, check_cancel
from ...interaction import CliInteractionProvider, InteractionProvider
from ...utils import image as img_utils
from ...utils import caption as cap_utils
from ...utils import report as rpt

from . import vlm

BBOX_PREFIX = "plk_bbox__"


def _is_bbox_artifact(path: Path) -> bool:
    return path.stem.startswith(BBOX_PREFIX)


def _clean_bbox_artifacts(folder: Path) -> None:
    for path in folder.iterdir():
        if path.is_file() and path.stem.startswith(BBOX_PREFIX):
            path.unlink(missing_ok=True)


def _bbox_stem(source: Path, index: int) -> str:
    return f"{BBOX_PREFIX}{source.stem}__{index:02d}"


def _save_bbox_training_item(
    crop,
    source_path: Path,
    output_dir: Path,
    caption: str,
    concept_token: str | None,
) -> dict:
    count = len(list(output_dir.glob(f"{BBOX_PREFIX}{source_path.stem}__*.png"))) + 1
    stem = _bbox_stem(source_path, count)
    img_path = output_dir / f"{stem}.png"
    txt_path = output_dir / f"{stem}.txt"

    final_caption = cap_utils.strip_boilerplate(caption)
    if concept_token and final_caption and not cap_utils.token_present(final_caption, concept_token):
        final_caption = f"{concept_token}, {final_caption}"

    crop.convert("RGB").save(img_path)
    txt_path.write_text(final_caption, encoding="utf-8")
    return {
        "caption": final_caption,
        "crop_path": str(img_path),
        "crop_name": img_path.name,
        "sidecar_path": str(txt_path),
    }

# ── Main ──────────────────────────────────────────────────────────────────────

def run(
    dataset_dir: Path,
    concept_token: str | None = None,
    output_dir: Path | None = None,
    qwen_model_id: str = "Qwen/Qwen2-VL-7B-Instruct",
    spot_check_pct: float = 0.10,
    overwrite: bool = False,
    report_path: Path | None = None,
    quantization: str = "none",
    dtype: str = "bfloat16",
    max_new_tokens: int = 200,
    max_pixels: int = vlm._DEFAULT_MAX_PIXELS,
    interaction: InteractionProvider | None = None,
    enabled_substeps: list[str] | None = None,
    cancel_check: CancelCheck | None = None,
) -> dict:
    style_mode = not concept_token
    rpt.step_header(5, "Caption — Bbox Annotation + Qwen3-VL")
    enabled = set(enabled_substeps or ["s5_1_annotate", "s5_2_caption", "s5_3_validate"])

    output_dir = output_dir or dataset_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if overwrite:
        _clean_bbox_artifacts(output_dir)

    all_images = img_utils.iter_images(dataset_dir)
    images = [p for p in all_images if not _is_bbox_artifact(p)]
    if not all_images:
        rpt.warn(f"No images in {dataset_dir}")
        return {}

    if style_mode:
        rpt.info(f"Captioning {len(images)} images in style mode (no concept token).")
    else:
        rpt.info(f"Captioning {len(images)} images. Concept token: '{concept_token}'")

    check_cancel(cancel_check)
    img_utils.materialize(all_images, dataset_dir, output_dir)

    captions: dict[str, str] = {}
    annotation_log: dict[str, list] = {}
    skipped_annotation: list[str] = []
    skip_all = False
    provider = interaction or CliInteractionProvider()
    runtime = vlm.CaptionRuntime(
        qwen_model_id,
        quantization=quantization,
        dtype=dtype,
        max_pixels=max_pixels,
    )

    try:
        # In-UI "Box Caption" callback: caption and persist a single cropped region.
        def _region_captioner(crop, metadata=None):
            check_cancel(cancel_check)
            source_raw = (metadata or {}).get("source_path") or (metadata or {}).get("image_path")
            if not source_raw:
                raise ValueError("Region caption metadata missing source_path")
            source_path = Path(source_raw)
            text = runtime.caption_region(crop)
            check_cancel(cancel_check)
            result = _save_bbox_training_item(crop, source_path, output_dir, text, concept_token)
            captions[result["crop_path"]] = result["caption"]
            return result

        for path in images:
            check_cancel(cancel_check)
            txt_path = output_dir / (path.stem + ".txt")
            if txt_path.exists() and not overwrite:
                caption = txt_path.read_text(encoding="utf-8").strip()
                captions[str(path)] = caption
                rpt.info(f"Skip (exists): {path.name}")
                continue

            # Phase 5A: bbox annotation ("Skip All" suppresses the UI for all remaining images)
            if "s5_2_caption" not in enabled:
                rpt.info(f"Caption substep disabled for {path.name}; preserving existing sidecar if present.")
                if txt_path.exists():
                    captions[str(path)] = txt_path.read_text(encoding="utf-8").strip()
                continue

            if "s5_1_annotate" not in enabled:
                annotations, skipped = [], True
            elif skip_all:
                annotations, skipped = [], True
            else:
                annotations, skipped, skip_all = provider.annotate_image(
                    path, captioner=_region_captioner
                )
            check_cancel(cancel_check)
            annotation_log[str(path)] = annotations
            if skipped:
                skipped_annotation.append(str(path))

            # Phase 5B: caption the whole original image after annotation is submitted.
            try:
                check_cancel(cancel_check)
                caption = runtime.caption_image(
                    path,
                    annotations,
                    concept_token,
                    max_new_tokens=max_new_tokens,
                )
                check_cancel(cancel_check)
            except CancelledRun:
                raise
            except Exception as exc:
                raise RuntimeError(f"VL captioning failed for {path.name}: {exc}") from exc

            # Clean
            caption = cap_utils.strip_boilerplate(caption)

            # Token enforcement — concept mode only
            if not style_mode and concept_token:
                if not cap_utils.token_present(caption, concept_token):
                    rpt.warn(f"Concept token missing in caption for {path.name} — appending.")
                    caption = f"{concept_token}, {caption}"

            check_cancel(cancel_check)
            txt_path.write_text(caption, encoding="utf-8")
            captions[str(path)] = caption
            rpt.ok(f"{path.name} → {caption[:80]}…" if len(caption) > 80 else f"{path.name} → {caption}")

        check_cancel(cancel_check)

        # Token consistency check — concept mode only
        missing_token: list[str] = []
        if "s5_3_validate" in enabled and not style_mode and concept_token:
            missing_token = cap_utils.verify_token_consistency(captions, concept_token)
            if missing_token:
                rpt.warn(f"Token '{concept_token}' missing in {len(missing_token)} captions:")
            for p in missing_token:
                check_cancel(cancel_check)
                rpt.warn(f"  {Path(p).name}")

        # Caption length outliers
        short = (
            [p for p, c in captions.items() if not cap_utils.caption_length_ok(c, min_chars=10)]
            if "s5_3_validate" in enabled
            else []
        )
        long_ = (
            [p for p, c in captions.items() if not cap_utils.caption_length_ok(c, max_chars=600)]
            if "s5_3_validate" in enabled
            else []
        )
        if short:
            rpt.warn(f"{len(short)} captions suspiciously short (< 10 chars)")
        if long_:
            rpt.warn(f"{len(long_)} captions very long (> 600 chars)")

        # Spot-check
        sample = []
        if "s5_3_validate" in enabled and captions:
            n_check = max(1, int(len(captions) * spot_check_pct))
            sample = random.sample(list(captions.items()), min(n_check, len(captions)))
            from rich.table import Table
            from rich import box
            from ...utils.report import console
            t = Table(title=f"Spot-check ({n_check} / {len(captions)})", box=box.SIMPLE_HEAVY)
            t.add_column("File", style="cyan", max_width=35)
            t.add_column("Caption", style="white")
            for p, c in sample:
                check_cancel(cancel_check)
                t.add_row(Path(p).name, c[:120] + ("…" if len(c) > 120 else ""))
            console.print(t)

        report = {
            "total": len(images),
            "captioned": len(captions),
            "skipped_annotation": skipped_annotation,
            "missing_token": missing_token,
            "short_captions": short,
            "long_captions": long_,
            "spot_check_sample": [p for p, _ in sample] if captions else [],
            "substeps": {
                "s5_1_annotate": {"enabled": "s5_1_annotate" in enabled},
                "s5_2_caption": {"enabled": "s5_2_caption" in enabled},
                "s5_3_validate": {"enabled": "s5_3_validate" in enabled},
            },
        }
        check_cancel(cancel_check)
        rpt.save_report(report, report_path or (output_dir / "step5_report.json"))
        return report
    finally:
        runtime.unload()
