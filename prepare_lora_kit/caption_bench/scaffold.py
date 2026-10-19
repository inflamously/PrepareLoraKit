"""Locating suites by name and scaffolding a new one (`plk caption-bench init`)."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from prepare_lora_kit import paths
from prepare_lora_kit.caption_bench.suite import IMAGE_SUFFIXES, SUITE_FILE

# Written as text, not dumped YAML, so the comments survive as the suite's own docs.
_BENCH_TEMPLATE = """\
# Caption benchmark suite. Docs: docs/caption-step/benchmark.md
name: {name}

# Trigger word for every image (a case can override it, or set null for style mode).
concept_token: {token}

# CaptionBboxConfig settings shared by every variant.
defaults:
  caption_model_id: {model}
  # vram_tier: low

# Leave `images` out to caption every file in images/ with no boxes.
# List them to add notes (what the caption SHOULD say) and annotations:
# images:
#   - path: images/burger.png
#     notes: invented food item, should be called krustekrabbe
#     annotations:
#       - {{label: sesame claws, x1: 0.1, y1: 0.1, x2: 0.4, y2: 0.4}}
#   - path: images/beach.png
#     concept_token: null
"""

_VARIANT_EXAMPLE = """\
# Example variant: any CaptionBboxConfig field. Run with: -v single
caption_strategy: single
"""


@dataclass(frozen=True)
class InitResult:
    root: Path
    copied: int


def resolve_suite_path(ref: str | Path) -> Path:
    """A path as given, or a bare name under ``~/.prepare_lora_kit/bench``.

    A bare name (no separator) that is not an existing folder in the current
    directory is treated as a suite name, so ``plk caption-bench run food`` works
    from anywhere.
    """
    path = Path(ref).expanduser()
    if len(path.parts) == 1 and not path.is_dir():
        return paths.BENCH_DIR / path
    return path


def suite_ref(root: Path) -> str:
    """The shortest SUITE argument that resolves back to ``root``."""
    root = Path(root)
    return root.name if root.parent == paths.BENCH_DIR else str(root)


def init_suite(
        root: Path,
        *,
        model_id: str | None = None,
        concept_token: str | None = None,
        images_from: Path | None = None,
) -> InitResult:
    """Create ``bench.yaml``, ``images/`` and an example variant; never overwrites."""
    root = Path(root)
    if (root / SUITE_FILE).exists():
        raise ValueError(f"{root} already has a {SUITE_FILE}")
    (root / "images").mkdir(parents=True, exist_ok=True)
    (root / "variants").mkdir(exist_ok=True)
    (root / SUITE_FILE).write_text(_BENCH_TEMPLATE.format(
        name=root.name,
        token=concept_token or "null",
        model=model_id or "Qwen/Qwen3-VL-8B-Instruct",
    ), encoding="utf-8")
    example = root / "variants" / "single.yaml"
    if not example.exists():
        example.write_text(_VARIANT_EXAMPLE, encoding="utf-8")
    copied = _copy_images(images_from, root / "images") if images_from else 0
    return InitResult(root=root, copied=copied)


def _copy_images(source: Path, dest: Path) -> int:
    """Copy the top-level images of ``source`` (not region crops) into ``dest``."""
    copied = 0
    for path in sorted(Path(source).iterdir()):
        if (not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES
                or path.name.startswith("plk_bbox__")):
            continue
        target = dest / path.name
        if not target.exists():
            shutil.copy2(path, target)
            copied += 1
    return copied
