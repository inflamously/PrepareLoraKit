"""
Step 2 — Curation

1. Perceptual-hash dedupe (phash, Hamming ≤ 8).
2. CLIP coverage: UMAP scatter (N > 30) or PIL grid mosaic (N ≤ 30).
3. Occlusion filter via CLIP zero-shot.
"""
from __future__ import annotations
from pathlib import Path

from ..utils import image as img_utils
from ..utils import report as rpt

HASH_DISTANCE = 8
OCCLUSION_THRESHOLD = 0.35   # below this CLIP score → flag as occluded


# ── Perceptual hash dedupe ────────────────────────────────────────────────────

def _compute_hashes(paths: list[Path]) -> dict[Path, object]:
    import imagehash
    from PIL import Image
    hashes = {}
    for p in paths:
        try:
            hashes[p] = imagehash.phash(Image.open(p).convert("RGB"))
        except Exception as exc:
            rpt.warn(f"Hash failed for {p.name}: {exc}")
    return hashes


def _find_duplicates(hashes: dict[Path, object]) -> list[tuple[Path, Path, int]]:
    """Return list of (path_a, path_b, hamming_distance) for near-duplicate pairs."""
    items = list(hashes.items())
    dupes = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            dist = items[i][1] - items[j][1]
            if dist <= HASH_DISTANCE:
                dupes.append((items[i][0], items[j][0], dist))
    return dupes


def _resolve_duplicates(
    pairs: list[tuple[Path, Path, int]],
    auto_drop: bool = True,
) -> set[Path]:
    """Return set of paths to drop. Auto-drops the blurrier of each pair."""
    from ..utils.image import blur_score
    to_drop: set[Path] = set()
    for a, b, dist in pairs:
        if a in to_drop or b in to_drop:
            continue
        blur_a = blur_score(a)
        blur_b = blur_score(b)
        drop = a if blur_a <= blur_b else b
        keep = b if drop is a else a
        if auto_drop:
            to_drop.add(drop)
            rpt.warn(f"DEDUPE drop {drop.name} (blur={blur_a if drop==a else blur_b:.1f}) "
                     f"← dupe of {keep.name} (dist={dist})")
        else:
            # easygui tie-break
            try:
                import easygui
                choice = easygui.buttonbox(
                    f"Near-duplicate pair (Hamming={dist}):\n\nA: {a.name}  (blur={blur_a:.1f})\n"
                    f"B: {b.name}  (blur={blur_b:.1f})\n\nWhich to DROP?",
                    title="Step 2 — Dedupe",
                    choices=[f"Drop {a.name}", f"Drop {b.name}", "Keep both"],
                )
                if choice and "Drop " in choice:
                    dropped = a if a.name in choice else b
                    to_drop.add(dropped)
            except ImportError:
                to_drop.add(drop)
    return to_drop


# ── Coverage visualisation ────────────────────────────────────────────────────

def _clip_embeddings(paths: list[Path]) -> "np.ndarray":
    import torch
    import numpy as np
    from PIL import Image
    from transformers import CLIPModel, CLIPProcessor

    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    model.eval()

    embeddings = []
    for p in paths:
        image = Image.open(p).convert("RGB")
        inputs = processor(images=image, return_tensors="pt")
        with torch.no_grad():
            feat = model.get_image_features(**inputs)
        embeddings.append(feat[0].cpu().numpy())
    return np.stack(embeddings)


def _save_umap(embeddings, paths: list[Path], out_path: Path) -> None:
    import numpy as np
    import matplotlib.pyplot as plt
    from umap import UMAP

    reducer = UMAP(n_components=2, random_state=42)
    coords = reducer.fit_transform(embeddings)

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.scatter(coords[:, 0], coords[:, 1], alpha=0.7, s=60)
    for i, p in enumerate(paths):
        ax.annotate(p.name[:20], (coords[i, 0], coords[i, 1]), fontsize=6, alpha=0.6)
    ax.set_title("Dataset Coverage — CLIP UMAP")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    rpt.ok(f"Coverage UMAP saved → {out_path}")


def _save_grid(paths: list[Path], out_path: Path, thumb: int = 256) -> None:
    import math
    from PIL import Image

    n = len(paths)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    grid = Image.new("RGB", (cols * thumb, rows * thumb), (30, 30, 30))
    for idx, p in enumerate(paths):
        try:
            img = Image.open(p).convert("RGB")
            img.thumbnail((thumb, thumb))
            r, c = divmod(idx, cols)
            grid.paste(img, (c * thumb, r * thumb))
        except Exception:
            pass
    grid.save(out_path)
    rpt.ok(f"Coverage grid saved → {out_path}")


# ── Occlusion filter ──────────────────────────────────────────────────────────

def _occlusion_scores(paths: list[Path]) -> dict[Path, float]:
    import torch
    from PIL import Image
    from transformers import CLIPModel, CLIPProcessor

    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    model.eval()

    prompts = [
        "a photo where the main subject is fully visible and unoccluded",
        "a photo where the main subject is partially hidden or occluded",
    ]
    scores = {}
    for p in paths:
        image = Image.open(p).convert("RGB")
        inputs = processor(text=prompts, images=image, return_tensors="pt", padding=True)
        with torch.no_grad():
            logits = model(**inputs).logits_per_image[0]
            prob_clear = float(logits.softmax(dim=0)[0].item())
        scores[p] = prob_clear
    return scores


# ── Main ──────────────────────────────────────────────────────────────────────

def run(
    dataset_dir: Path,
    output_dir: Path | None = None,
    auto_dedupe: bool = True,
    skip_clip: bool = False,
) -> dict:
    rpt.step_header(2, "Curation — Dedupe + Coverage")

    output_dir = output_dir or dataset_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    images = img_utils.iter_images(dataset_dir)
    if not images:
        rpt.warn(f"No images in {dataset_dir}")
        return {}

    rpt.info(f"Found {len(images)} images. Computing perceptual hashes …")
    hashes = _compute_hashes(images)

    pairs = _find_duplicates(hashes)
    rpt.info(f"Near-duplicate pairs: {len(pairs)}")
    to_drop = _resolve_duplicates(pairs, auto_drop=auto_dedupe) if pairs else set()

    kept_images = [p for p in images if p not in to_drop]
    rpt.ok(f"After dedupe: {len(kept_images)} images ({len(to_drop)} dropped)")

    # Coverage
    coverage_path: Path | None = None
    if not skip_clip:
        try:
            if len(kept_images) > 30:
                rpt.info("Computing CLIP embeddings for UMAP coverage …")
                emb = _clip_embeddings(kept_images)
                coverage_path = output_dir / "coverage_umap.png"
                _save_umap(emb, kept_images, coverage_path)
            else:
                coverage_path = output_dir / "coverage_grid.png"
                _save_grid(kept_images, coverage_path)
        except Exception as exc:
            rpt.warn(f"Coverage visualisation failed: {exc}")

    # Occlusion filter
    occluded: list[str] = []
    if not skip_clip:
        try:
            rpt.info("Running occlusion filter (CLIP zero-shot) …")
            occ_scores = _occlusion_scores(kept_images)
            occluded = [str(p) for p, s in occ_scores.items() if s < OCCLUSION_THRESHOLD]
            if occluded:
                rpt.warn(f"{len(occluded)} images flagged as possibly occluded/ambiguous:")
                for o in occluded:
                    rpt.warn(f"  {Path(o).name}")
        except Exception as exc:
            rpt.warn(f"Occlusion filter failed: {exc}")

    report = {
        "duplicate_pairs": [(str(a), str(b), d) for a, b, d in pairs],
        "dropped_duplicates": [str(p) for p in to_drop],
        "kept_images": [str(p) for p in kept_images],
        "occluded_flagged": occluded,
        "coverage_image": str(coverage_path) if coverage_path else None,
    }
    rpt.save_report(report, output_dir / "step2_report.json")
    return report
