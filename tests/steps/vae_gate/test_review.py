import numpy as np
from PIL import Image

from prepare_lora_kit.steps.vae_gate.review import _save_review_artifacts


def test_save_review_artifacts_writes_review_only_diff_and_hard_mask(tmp_path):
    original = tmp_path / "input.png"
    Image.new("RGB", (4, 4), (10, 10, 10)).save(original)
    recon = np.full((4, 4, 3), 10, dtype=np.uint8)
    recon[1:3, 1:3] = (240, 240, 240)

    artifact = _save_review_artifacts(
        original,
        recon,
        tmp_path / "reports" / "VaeGateStep_previews",
        diff_amplification=2.0,
        gaussian_blur_sigma=0.0,
        gaussian_blur_kernel=1,
        otsu_enabled=False,
    )

    assert artifact["width"] == 4
    assert artifact["height"] == 4
    assert (tmp_path / "reports" / "VaeGateStep_previews").exists()
    assert not (tmp_path / "vae.png").exists()

    hard = np.array(Image.open(artifact["views"]["hard"]).convert("RGB"))
    assert set(np.unique(hard).tolist()) <= {0, 255}

    diff = Image.open(artifact["views"]["diff"])
    vae = Image.open(artifact["views"]["vae"])
    assert diff.size == (4, 4)
    assert vae.size == (4, 4)


def test_review_artifact_output_flags_control_written_views(tmp_path):
    original = tmp_path / "image.png"
    Image.new("RGB", (4, 4), (10, 10, 10)).save(original)
    recon = np.full((4, 4, 3), 20, dtype=np.uint8)

    artifact = _save_review_artifacts(
        original,
        recon,
        tmp_path / "previews",
        output_preview=False,
        output_silhouette=True,
        output_hard_silhouette=False,
    )

    assert set(artifact["views"]) == {"original", "diff"}
    artifact_dir = next((tmp_path / "previews").iterdir())
    assert not (artifact_dir / "vae.png").exists()
    assert (artifact_dir / "diff.png").exists()
    assert not (artifact_dir / "hard.png").exists()
