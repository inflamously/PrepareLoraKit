def test_mock_vae_gate_decisions_apply_only_to_original_dataset_images(tmp_path, make_image):
    from prepare_lora_kit.invoke import _mock_vae_gate

    working_dir = tmp_path / "run" / "dataset"
    output_dir = tmp_path / "run"
    working_dir.mkdir(parents=True)
    first = working_dir / "first.png"
    second = working_dir / "second.png"
    make_image(first)
    make_image(second)

    class FakeInteraction:
        def vae_review(self, items):
            assert all(
                str(output_dir / "reports" / "VaeGateStep_previews") in item["views"]["vae"]
                for item in items
            )
            return {
                str(first.resolve()): "drop",
                str(second.resolve()): "replace",
            }

    report = _mock_vae_gate(working_dir, output_dir, interaction=FakeInteraction())

    assert not first.exists()
    assert second.exists()
    assert report["needs_replacement"] == [str(second)]
    assert not list(working_dir.glob("vae.png"))
    assert list((output_dir / "reports" / "VaeGateStep_previews").glob("*/vae.png"))
