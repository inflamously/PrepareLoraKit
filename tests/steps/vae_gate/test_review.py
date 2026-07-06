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
