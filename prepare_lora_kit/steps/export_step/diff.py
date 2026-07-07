"""Compute the export diff between the finalized dataset and the target folder.

Pure functions only — no writes. The step module renders this diff for review
before any copy happens. A *finalized* dataset image is one that has a matching
``.txt`` caption sidecar beside it (the ai-toolkit training convention); images
without a caption are not exported.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path


from prepare_lora_kit.utils import image as img_utils
CAPTION_SUFFIX = ".txt"


@dataclass
class DiffEntry:
    """One finalized image + caption pair, classified against the target."""

    rel: str                 # target-relative image path (posix)
    image_src: str           # absolute source image path in the dataset
    caption_src: str | None  # absolute source .txt path (always set for finalized pairs)
    image_status: str        # "added" | "modified" | "unchanged"
    caption_status: str      # "added" | "modified" | "unchanged"


@dataclass
class ExportDiff:
    """Categorized export plan for one dataset → target comparison."""

    target_dir: str
    added: list[DiffEntry] = field(default_factory=list)
    modified: list[DiffEntry] = field(default_factory=list)
    unchanged: list[DiffEntry] = field(default_factory=list)
    orphaned: list[str] = field(default_factory=list)  # target images not in the final set

    @property
    def changed(self) -> list[DiffEntry]:
        """Entries that would actually be written (added + modified)."""
        return [*self.added, *self.modified]

    def counts(self) -> dict[str, int]:
        return {
            "added": len(self.added),
            "modified": len(self.modified),
            "unchanged": len(self.unchanged),
            "orphaned": len(self.orphaned),
        }


def _file_digest(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def _classify(src: Path, dst: Path) -> str:
    """Return "added" | "modified" | "unchanged" for a src→dst copy."""
    if not dst.exists():
        return "added"
    if src.stat().st_size != dst.stat().st_size:
        return "modified"
    return "unchanged" if _file_digest(src) == _file_digest(dst) else "modified"


def compute_diff(dataset_dir: Path, target_dir: Path) -> ExportDiff:
    """Classify each finalized dataset pair against ``target_dir``.

    Subject subfolders are preserved: a dataset image ``subject/image_01.png``
    maps to ``target/subject/image_01.png`` (+ ``image_01.txt``). Images already
    in the target that are no longer in the final set are reported as
    ``orphaned`` and are never touched.
    """
    dataset_dir = Path(dataset_dir)
    target_dir = Path(target_dir)
    diff = ExportDiff(target_dir=str(target_dir))
    final_rels: set[str] = set()

    for image in img_utils.iter_images(dataset_dir):
        caption = image.with_suffix(CAPTION_SUFFIX)
        if not caption.exists():
            continue  # not finalized — no caption sidecar
        rel = image.relative_to(dataset_dir)
        rel_posix = rel.as_posix()
        final_rels.add(rel_posix)

        dst_image = target_dir / rel
        dst_caption = dst_image.with_suffix(CAPTION_SUFFIX)
        entry = DiffEntry(
            rel=rel_posix,
            image_src=str(image),
            caption_src=str(caption),
            image_status=_classify(image, dst_image),
            caption_status=_classify(caption, dst_caption),

        )
        if entry.image_status == "added":
            diff.added.append(entry)
        elif entry.image_status == "modified" or entry.caption_status != "unchanged":
            diff.modified.append(entry)
        else:
            diff.unchanged.append(entry)

    if target_dir.exists():
        for img in img_utils.iter_images(target_dir):
            rel_posix = img.relative_to(target_dir).as_posix()
            if rel_posix not in final_rels:
                diff.orphaned.append(rel_posix)
        diff.orphaned.sort()

    return diff
