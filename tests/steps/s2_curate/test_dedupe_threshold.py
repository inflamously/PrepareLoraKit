"""Tests that the configurable dedup threshold is honored end-to-end."""
from pathlib import Path

from prepare_lora_kit import invoke
from prepare_lora_kit.project.configs import CurateConfig
from prepare_lora_kit.project.registry import _default_pipeline
from prepare_lora_kit.steps.s2_curate import dedupe


class _FakeHash:
    """Minimal stand-in for an imagehash hash: subtraction yields Hamming distance."""

    def __init__(self, bits: int) -> None:
        self.bits = bits

    def __sub__(self, other: "_FakeHash") -> int:
        return abs(self.bits - other.bits)


def test_find_duplicates_respects_max_distance():
    # Two hashes exactly 5 apart.
    hashes = {Path("a.png"): _FakeHash(0), Path("b.png"): _FakeHash(5)}

    # Loose threshold flags the pair...
    assert len(dedupe._find_duplicates(hashes, max_distance=8)) == 1
    # ...stricter threshold does not.
    assert dedupe._find_duplicates(hashes, max_distance=3) == []


def test_find_duplicates_default_matches_module_constant():
    hashes = {Path("a.png"): _FakeHash(0), Path("b.png"): _FakeHash(dedupe.HASH_DISTANCE)}
    # Pair sits exactly at the module-default boundary, so it is flagged by default.
    assert len(dedupe._find_duplicates(hashes)) == 1


def test_invoke_curate_forwards_threshold_config(tmp_path, monkeypatch):
    captured = {}

    def _fake_run(*args, **kwargs):
        captured.update(kwargs)
        return {}

    from prepare_lora_kit.steps import s2_curate
    monkeypatch.setattr(s2_curate, "run", _fake_run)

    working = tmp_path / "dataset"
    working.mkdir()
    cfg = CurateConfig(
        dedup_hamming_distance=7,
        pca_umap_switch_threshold=42,
    )

    invoke._invoke_CurateStep(working, tmp_path, cfg)

    assert captured["dedup_hamming_distance"] == 7
    assert captured["pca_umap_switch_threshold"] == 42


def test_default_dedup_distance_is_conservative():
    assert CurateConfig().dedup_hamming_distance == 3
    curate = next(s for s in _default_pipeline() if s["type"] == "CurateStep")
    assert curate["dedup_hamming_distance"] == 3
