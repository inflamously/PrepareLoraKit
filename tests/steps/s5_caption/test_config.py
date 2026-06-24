from prepare_lora_kit.project.configs import CaptionConfig


def test_caption_config_defaults_to_auto_vram():
    cfg = CaptionConfig()

    assert cfg.caption_model_id is None
    assert cfg.caption_model_task == "auto"
    assert cfg.vram_tier == "auto"
    assert cfg.quantization == "auto"


def test_caption_config_maps_legacy_qwen_model_id():
    cfg = CaptionConfig(qwen_model_id=" Qwen/Qwen2.5-VL-3B-Instruct ")

    assert cfg.caption_model_id == "Qwen/Qwen2.5-VL-3B-Instruct"
