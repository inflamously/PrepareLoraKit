# Caption model integration tests

These tests download real Hugging Face models, load them on CUDA, send a tiny
image through the production caption runtime, and verify that the multimodal
prompt and response parser return `hello world`. They are skipped during normal
test runs.

Enable only the model or models you want to exercise:

| Model | Opt-in environment variable |
|---|---|
| Qwen3.8 27B | `PLK_RUN_QWEN38_INTEGRATION=1` |
| Qwen3-VL 2B | `PLK_RUN_QWEN3_VL_2B_INTEGRATION=1` |
| Qwen3-VL 4B | `PLK_RUN_QWEN3_VL_4B_INTEGRATION=1` |
| Qwen3-VL 8B | `PLK_RUN_QWEN3_VL_8B_INTEGRATION=1` |
| Qwen2.5-VL 3B | `PLK_RUN_QWEN25_VL_3B_INTEGRATION=1` |
| Qwen2.5-VL 7B | `PLK_RUN_QWEN25_VL_7B_INTEGRATION=1` |
| Qwen2-VL 7B | `PLK_RUN_QWEN2_VL_7B_INTEGRATION=1` |
| JoyCaption Beta One | `PLK_RUN_JOYCAPTION_INTEGRATION=1` |

For example:

```bash
PLK_RUN_QWEN3_VL_4B_INTEGRATION=1 \
PLK_CAPTION_INTEGRATION_QUANTIZATION=4bit \
pytest -q -s tests/integration/steps/caption_bbox/test_catalog_models.py
```

The catalog tests use `auto` quantization by default. Override them with
`PLK_CAPTION_INTEGRATION_QUANTIZATION=auto|4bit|8bit|none`. The Qwen3.8 test
keeps its existing `PLK_QWEN38_QUANTIZATION` setting and defaults to `8bit`.

To run all eight models sequentially in fresh Python processes:

```bash
python scripts/run_caption_integration_tests.py
```

The runner defaults every model to 8-bit loading. Use, for example,
`--quantization 4bit` to change all runs. Extra pytest options go after `--`.
