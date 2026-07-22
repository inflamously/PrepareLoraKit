# Caption Step — CaptionBboxStep Architecture

The reference for the captioning stage: how `CaptionBboxStep` is layered, how bbox
annotation and captioning are coupled, how the VLM runtime is loaded and cached,
and how progress reaches the UI. Read this before changing anything under
`prepare_lora_kit/steps/caption_bbox/`.

Paths below are relative to the repository root.

## Overview

`CaptionBboxStep` is a single pipeline step at **order 4**, with direct
prerequisites `QualityGateStep` and `CurateStep` (declared in
`prepare_lora_kit/pipeline/configuration.py`). It carries two coupled concerns —
region annotation and caption generation — exposed as three substeps.

It is the only step flagged `resume_aware=True`, meaning the engine never skips it
and the step performs its own per-image resume. It is also the only step with a
bespoke live-progress channel that bypasses the normal `ExecutionHooks` system.

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
| `real.py` | `RealCaptionStep(CaptionStep)` — captions via `vlm.CaptionRuntime`; loads/unloads the model and runs full validation. |
| `mock.py` | `MockCaptionStep(CaptionStep)` — deterministic `--mock` captions, no model, empty validation. Also the `_mock_caption()` back-compat wrapper. |
| `step.py` | Thin `run()` wrapper → `RealCaptionStep(...).run()`; keeps the public signature and back-compat re-exports. |
| `prompts.py` | Built-in prompt templates, `build_full_image_prompt`, `describe_box_position`, placeholder application, and caption text-QA helpers (`strip_boilerplate`, `caption_length_ok`, …). |
| `vlm.py` | HF caption runtime: `CaptionRuntime`, `LoadedCaptionModel`, model loading/quantization/device, generation adapters. |
| `workflow.py` | Per-image decision workflow: `gather_decisions`, `resolve_decision`, `_caption_full_image`, `_write_caption`. |
| `artifacts.py` | Bbox crop/sidecar persistence: `save_boxes_sidecar`, `load_boxes_sidecar`, `_save_bbox_training_item`, `BBOX_PREFIX`. |
| `validation.py` | Caption cleanup + QA: `clean_caption_for_mode`, `validate_captions`, `render_spot_check`. |
| `reports.py` | Report payload builders: `substep_status` (reads `SUBSTEP_REGISTRY`), `build_success_report`, `save_success_report`, `_save_failure_report`. |
| `regions.py` | `make_region_captioner(caption_fn=…)` — the closure the UI calls to caption and persist a single drawn crop. |

Adjacent files:

| File | Role |
|---|---|
| `prepare_lora_kit/invoke/caption_bbox_step.py` | Invoke adapter; dispatches to `MockCaptionStep` or the real `run()` wrapper. |
| `prepare_lora_kit/caption_prompts/prompt_registry.py` | User prompt library CRUD over `configs/caption_prompts/` (imports templates from `steps/caption_bbox/prompts.py`). |
| `prepare_lora_kit/pipeline/configs/caption_bbox_config.py` | 63 | `CaptionBboxConfig` runtime dataclass. |
| `prepare_lora_kit/project/config_schema/steps/caption_bbox.py` | 44 | UI field schema and the curated model list. |

## Substeps

Registered in `prepare_lora_kit/project/pipeline/substeps.py`:

```python
"CaptionBboxStep": (
    SubstepDefinition("annotate_regions", "Annotate regions"),
    SubstepDefinition("caption_images", "Caption images"),
    SubstepDefinition("validate_captions", "Validate captions",
                      prerequisites=("caption_images",)),
),
```

All three are non-optional and enabled by default. What each toggle does when
**disabled**:

- `annotate_regions` — `gather_decisions` short-circuits to empty annotations for
  every image. The same happens automatically when `interaction is None`, i.e. on
  the CLI and in headless runs, so the step degrades to plain captioning.
- `caption_images` — `gather_decisions` returns `{}` and `resolve_decision`
  returns `None`. Existing `.txt` sidecars are preserved and the report is rebuilt
  from them. Bbox sidecars survive untouched.
- `validate_captions` — `validate_captions` and `render_spot_check` return empty.
  Declares a prerequisite on `caption_images`.

Selection flows `pipeline/execution/selection.py` → `engine._invoke_step` →
adapter `enabled_substeps` kwarg → `run()`, where it becomes the `enabled` set.

## How bbox and caption are coupled

Boxes are not a separate output — they feed the caption prompt. Each annotation is
turned into prose by `steps/caption_bbox/prompts.py::describe_box_position(x1, y1, x2, y2)`
("in the upper-left", "a small element on the right"), combined with its label, and
injected into the `{bbox_annotations}` placeholder of the full-image prompt.

Separately, each drawn region can be captioned **on its own** in the UI, producing
an independent training pair: a crop PNG plus its caption `.txt`. So bbox work
yields both prompt context for the source image and extra dataset items.

## Control flow of `run()`

`steps/caption_bbox/base.py::CaptionStep.run()` (entered via the `step.py` wrapper
for the real step, or `MockCaptionStep` under `--mock`):

1. `style_mode = not concept_token`; substeps default to
   `substep_ids_for("CaptionBboxStep")` (read from `SUBSTEP_REGISTRY`).
2. Prepare the output dir (deliberately **not** wiping bbox artifacts), collect
   source images filtering out `plk_bbox__*`, materialize.
3. `_resolve_pending` — map each image to its `.txt`; pending is every image when
   `overwrite`, otherwise only those missing a caption.
4. Construct `vlm.CaptionRuntime`, and call `runtime.load()` **only if** there is
   pending work and `caption_images` is enabled.
5. `_caption_dataset`:
   - **Phase A** — `gather_decisions`: one batched annotation interaction covering
     all pending images (a single modal, not one per image).
   - **Phase B** — per pending image: `resolve_decision` → persist region caption
     edits → `save_boxes_sidecar` → `_caption_full_image` → `_write_caption`.
6. `_validate_and_save_success`: `validate_captions` + `render_spot_check` +
   `build_success_report` + `save_success_report`.
7. `finally: runtime.unload()` — clears `_CACHE` and empties the CUDA cache.

`check_cancel(cancel_check)` is called between phases and per image. On failure,
`_save_failure_report` writes a `{"status": "failed", ...}` payload before
re-raising.

## Model runtime (`vlm.py`)

**Backend-generic Hugging Face transformers**, not tied to one model family.
`task` is `auto | image-text-to-text | image-to-text`, and `auto` tries both
adapters in order:

- `image-text-to-text` — requires `processor.apply_chat_template`. Model class
  tried in order: `AutoModelForImageTextToText` → `AutoModelForVision2Seq` →
  `Qwen2VLForConditionalGeneration`. Sets `supports_prompt=True`.
- `image-to-text` — `AutoModelForVision2Seq` → `BlipForConditionalGeneration` →
  `VisionEncoderDecoderModel` → `AutoModelForCausalLM`. `supports_prompt=False`,
  so the caption is composed post-hoc (labels and the token are appended). Florence
  gets the special `<MORE_DETAILED_CAPTION>` task prompt.

Characteristics worth knowing:

- **No batching.** Strictly one image per `generate()` call, greedy
  (`do_sample=False`).
- **Lazy imports.** `torch`, `transformers` and `PIL` are imported inside
  functions, and `__init__.py` is a `__getattr__` shim, so nothing heavy loads
  until the step actually runs.
- **Caching.** Module-level `_CACHE` keyed by
  `(model_id, task, quantization, dtype, max_pixels)`, so region captions and
  full-image captions reuse one loaded model.
- **Thread safety.** `load()` is guarded by a `threading.Lock` because the UI's
  region-caption call arrives on a different thread than the pipeline loop.
- **Device.** `device_map="auto"` with `low_cpu_mem_usage=True`; `_input_device()`
  sniffs params → buffers → `model.device` → cuda/cpu fallback. `_resolve_dtype`
  forces float32 without CUDA.
- **Quantization.** `CaptionBboxConfig._VRAM_TIERS` maps the project's `vram_tier`
  to `(quantization, dtype)`: `low`→4bit, `mid`→8bit, `high`/`max`→none. The
  `auto` quantization mode instead picks 4bit ≤16 GB VRAM, 8bit ≤32 GB, else none.
  4-bit uses `BitsAndBytesConfig` nf4 with double quant, and 4/8-bit require CUDA
  plus bitsandbytes.
- **OOM defense.** `_DEFAULT_MAX_PIXELS = 1024 * 1024` area budget with a LANCZOS
  downscale before the processor, and a CUDA cache clear in the `finally` of every
  generate.

**This step runs in-process.** Unlike SeedVR2 upscaling
(`steps/upscale/seedvr2_worker.py`), there is no worker subprocess. VRAM hygiene
between steps comes from `release_accelerator_memory()` in
`pipeline/execution/engine.py` plus `runtime.unload()`.

## Resume semantics

`resume_aware=True` in `STEP_DEFINITIONS` means `StepSkipPolicy` returns no skip
reason for this step — the engine re-enters `run()` on every pipeline run, even
when state says done.

The real resume lives in `_resolve_pending()`: only images lacking a `.txt` are
pending (all of them when `overwrite`). If nothing is pending, the VLM is never
loaded at all and the report is rebuilt from the captions already on disk.

`--force` reaches the adapter as `overwrite=True`, and
`resolve_force_invalidated_steps()` also resets this step and everything
downstream in `.plk_state.json`.

## Artifacts written

- `{stem}.txt` — the training caption, beside each image in the working dataset.
- `plk_bbox__{stem}__{NN}.png` + matching `.txt` — one independent training pair
  per drawn region.
- `plk_bbox__{stem}__boxes.json` — reload sidecar with normalized coordinates,
  labels and `crop_name`. Writing an empty list deletes the file.
- `outputs/<name>/reports/CaptionBboxStep_report.json` — the step report. When
  `report_path` is `None`, the same `CaptionBboxStep_report.json` name is used
  under `output_dir` (`reports.py::_REPORT_NAME`).

The report payload (`reports.py::build_success_report`) carries `total`,
`captioned`, `caption_model`, `caption_status`, `skipped_annotation`,
`missing_token`, `short_captions`, `long_captions`, `spot_check_sample`, and a
`substeps` block recording which substeps were enabled.

## Prompts

Built-in templates live in `prepare_lora_kit/steps/caption_bbox/prompts.py`: a concept variant
(when `concept_token` is set), a style variant (when it is not), and a region
prompt. `default_prompt_text(kind)` is the single source of truth.

The user library is one YAML per prompt at
`configs/caption_prompts/<kind>__<slug>.yaml`, managed by
`caption_prompts/prompt_registry.py`. Kinds are `full_image` and `region`. The
`"Default"` entry is **virtual** — synthesized from `default_prompt_text`,
read-only, and cannot be saved or deleted. The directory is created on first save.

The selected text is stored on the project as `CaptionBboxConfig.caption_prompt`
and `region_prompt`; blank means use the built-in. Templating is plain replacement,
**not** `str.format`, so stray braces in prompts or captions are safe:

```python
def apply_prompt_placeholders(template, annotation_text, concept_token):
    return template.replace("{bbox_annotations}", annotation_text) \
                   .replace("{concept_token}", concept_token or "")
```

UI CRUD is exposed via `prepare_lora_kit_ui/bridge.py` as `list_caption_prompts`,
`save_caption_prompt` and `delete_caption_prompt`.

## UI plumbing

Two independent channels.

**Lifecycle — `ExecutionHooks`.** The generic mechanism
(`pipeline/execution/models.py`), implemented for the UI by
`prepare_lora_kit_ui/runner/execution_hooks.py::UiJobHooks`. Caveat: the engine
fires `substep_complete` for *all* substeps in a batch after `run()` returns
(`_record_completion`), because step invokers run their selected substeps as one
transaction. Substep granularity here is bookkeeping, not live progress.

**Live progress — `caption_status_callback`.** Threaded outside the hooks system:
`runner/run_request.py` puts `job.set_caption_status` into `invoke_kwargs`, the
adapter forwards it into `run()`, which passes it as `status_callback=` to
`CaptionRuntime`. `_emit_status` emits phases `loading | ready | captioning |
failed | unloaded`, with `current_image` during captioning and `error` on failure.
`job.set_caption_status` stores it under the job's condition lock; the frontend
renders it in `prepare_lora_kit_ui/static/caption/status.js`. The last payload is
also snapshotted into the report as `caption_status`.

**Interaction requests** — `prepare_lora_kit_ui/runner/interactions.py`:

- `annotate_dataset(images, *, captioner)` — sends one `bbox_annotation`
  `request_input` for the whole batch. Each item carries the media payload,
  prefilled annotations from the reload sidecar, and a `done` flag. It stashes the
  captioner and batch paths under a lock for the modal's lifetime, clearing them in
  `finally`.
- `caption_region(image_path, box)` — the live "caption this box" endpoint.
  Validates the image is in the active batch, crops with PIL from normalized
  coordinates, then calls the stashed `make_region_captioner` closure. Exposed
  through `bridge.py::caption_region(job_id, image_path, box)`.

Frontend lives in `prepare_lora_kit_ui/static/steps/bbox_annotation/`
(`bbox_annotation.js`, `canvas.js`, `box_panel.js`, `thumbnail_strip.js`,
`batch.js`). Providers without `annotate_dataset` — CLI and tests — fall back to
`prepare_lora_kit/interaction.py::annotate_dataset_via_images`, which loops the
per-image `annotate_image` hook.

## Known sharp edges

- `vlm.py` is ~600 lines, well over the ≤500-line convention in `CLAUDE.md`. It
  bundles model loading, quantization, device handling, prompt building and
  generation — see `docs/complexity-technical-debt.md`.

Resolved by the class refactor: the substep id list is no longer duplicated — every
consumer (`base.py`, `reports.py::substep_status`, the mock) reads it from
`SUBSTEP_REGISTRY` via `substep_ids_for("CaptionBboxStep")`. And the `--mock`
runtime is a `CaptionStep` subclass sharing the real orchestration instead of a
hand-maintained clone.
