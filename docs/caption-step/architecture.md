# Layering and file map

Part of the [Caption Step reference](README.md).

## Layering

```
pipeline/execution/engine.py::_invoke_step
  → STEP_INVOKE_MAP["CaptionBboxStep"]        (invoke/__init__.py)
    → invoke/caption_bbox_step.py             adapter: dataclass → flat kwargs
      → steps/caption_bbox/base.py::CaptionStep.run()   shared orchestration
         ├── real.py       RealCaptionStep  (VLM captions, subclass)
         ├── mock.py       MockCaptionStep  (deterministic --mock, subclass)
         ├── step.py       run() wrapper → RealCaptionStep
         ├── prompts.py    prompt templates + assembly + caption text-QA helpers
         ├── workflow.py   per-image decision loop
         ├── vlm.py        HF caption runtime
         ├── artifacts.py  bbox crops + boxes.json sidecars
         ├── validation.py caption cleanup / QA / spot check
         ├── reports.py    report payload builders
         └── regions.py    closure the UI calls to caption one crop
```

`base.py::CaptionStep` owns the whole per-image pipeline (output prep, resume, the
batch annotation interaction, the caption loop, validation, reporting). The real
and mock runtimes are **separate subclasses** — `RealCaptionStep` (`real.py`) and
`MockCaptionStep` (`mock.py`) — that override only the differing hooks
(`caption_full_image`, `_region_caption_fn`, runtime `prepare_runtime`/`teardown`,
`validate`, report metadata). The mock no longer re-implements the flow.

The adapter is the only layer that knows about `CaptionBboxConfig`. It unpacks the
dataclass into flat keyword arguments, injects the canonical report path, and
instantiates `MockCaptionStep` when `mock_runtime` is set (otherwise calls the
`step.py::run()` wrapper). Per-run UI overrides in `caption_runtime`
(`model_id` / `task` / `vram_mode`) win over the project config.

Note the adapter passes `output_dir=working_dir` — captions land beside the
images; only the report goes to `reports/`.

## File map

`prepare_lora_kit/steps/caption_bbox/`:

| File | Role |
|---|---|
| `__init__.py` | Lazy `__getattr__` re-export of `run` only, so importing the package does not pull in torch. |
| `base.py` | `CaptionStep` ABC: shared `run()` template + phase helpers (`_caption_dataset`, `_validate_and_save_success`, `_resolve_pending`) and the hooks the subclasses fill in. |
| `grounded.py` | `generate_grounded_caption(...)` — the observe → compose → gap-fill pipeline over one loaded VLM (prompt-capable models only). |
| `gap_fill.py` | The additive third pass: `needs_gap_pass` (gate), `parse_gap_phrases`, `merge_missing_phrases`. Pure text, no model. |
| `caption_text.py` | Caption *text* utilities: `strip_boilerplate`, `caption_length_ok`, token checks, plus the two "does the caption already say this?" tests shared by `gap_fill`, `grounded` and `validation` — strict `covered` (every content word) and lenient `mentions` (`head_noun` only). |
| `real.py` | `RealCaptionStep(CaptionStep)` — captions via `vlm.CaptionRuntime`; loads/unloads the model and runs full validation. |
| `mock.py` | `MockCaptionStep(CaptionStep)` — deterministic `--mock` captions, no model, empty validation. Also the `_mock_caption()` back-compat wrapper. |
| `step.py` | Thin `run()` wrapper → `RealCaptionStep(...).run()`; keeps the public signature and back-compat re-exports. |
| `prompts.py` | Built-in prompt templates, `build_full_image_prompt`, `describe_box_position`, placeholder application, and `apply_domain_brief`. |
| `vlm.py` | HF caption runtime: `CaptionRuntime`, `LoadedCaptionModel`, model loading/quantization/device, generation adapters. |
| `workflow.py` | Per-image decision workflow: `gather_decisions`, `resolve_decision`, `_caption_full_image`, `_write_caption`. |
| `artifacts.py` | Bbox crop/sidecar persistence: `save_boxes_sidecar`, `load_boxes_sidecar`, `_save_bbox_training_item`, `BBOX_PREFIX`. |
| `validation.py` | Caption cleanup + QA: `clean_caption_for_mode`, `enforce_region_labels`, `validate_captions`, `render_spot_check`. |
| `reports.py` | Report payload builders: `substep_status` (reads `SUBSTEP_REGISTRY`), `build_success_report`, `save_success_report`, `_save_failure_report`. |
| `regions.py` | `make_region_captioner(caption_fn=…)` — the closure the UI calls to caption and persist a single drawn crop. |

Adjacent files:

| File | Role |
|---|---|
| `prepare_lora_kit/invoke/caption_bbox_step.py` | Invoke adapter; dispatches to `MockCaptionStep` or the real `run()` wrapper. |
| `prepare_lora_kit/caption_prompts/prompt_registry.py` | User prompt library CRUD over `configs/caption_prompts/` (imports templates from `steps/caption_bbox/prompts.py`). |
| `prepare_lora_kit/pipeline/configs/caption_bbox_config.py` | `CaptionBboxConfig` runtime dataclass. |
| `prepare_lora_kit/project/config_schema/steps/caption_bbox.py` | UI field schema and the curated model list. |
