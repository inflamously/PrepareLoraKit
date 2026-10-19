"""Fixtures for the caption benchmark: a tiny synthetic suite on disk."""
from pathlib import Path

import pytest
from PIL import Image


def _write_image(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16), color).save(path)


@pytest.fixture
def suite_dir(tmp_path: Path) -> Path:
    """A two-image suite with one annotated case and a suite-wide token."""
    root = tmp_path / "suite"
    _write_image(root / "images" / "burger.png", (200, 40, 40))
    _write_image(root / "images" / "beach.png", (40, 120, 200))
    (root / "bench.yaml").write_text(
        """\
name: tiny
concept_token: krustekrabbe
defaults:
  caption_model_id: some/model
images:
  - path: images/burger.png
    notes: invented food item
    annotations:
      - {label: sesame claws, x1: 0.1, y1: 0.1, x2: 0.4, y2: 0.4}
  - path: images/beach.png
    concept_token: null
""",
        encoding="utf-8",
    )
    return root
