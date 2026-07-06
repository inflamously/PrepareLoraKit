from prepare_lora_kit_pipeline.configs import CaptionBboxConfig


def test_caption_bbox_config_defaults_to_auto_vram():
    cfg = CaptionBboxConfig()

    assert cfg.caption_model_id is None
    assert cfg.caption_model_task == "auto"
    assert cfg.vram_tier == "auto"
    assert cfg.quantization == "auto"


def test_caption_bbox_config_maps_legacy_qwen_model_id():
    cfg = CaptionBboxConfig(qwen_model_id=" Qwen/Qwen2.5-VL-3B-Instruct ")

    assert cfg.caption_model_id == "Qwen/Qwen2.5-VL-3B-Instruct"
