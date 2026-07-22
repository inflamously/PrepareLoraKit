# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PrepareLoraKit is a Python 3.10+ CLI (`plk`) and pywebview UI that prepares image datasets
for LoRA-style training. It takes an untouched source folder, builds a separate working dataset
under `outputs/<name>/dataset/`, runs the dataset pipeline, and emits per-step JSON reports plus
an optional export folder for the next training step.

## Commands

```bash
python main.py <cmd>          # run CLI from the checkout (or `plk <cmd>` after `pip install -e .`)
python main.py run -i /path/to/images -p example -t my_trigger   # full pipeline
python main.py step -s CaptionBboxStep -p example -i ... -o ... -t ... # single step by type
python main.py ui                 # launch the desktop webview UI (--mock <STEP> for fixture data)
python main.py projects           # list configs/projects/

pytest                            # full Python test suite
pytest tests/project/test_config.py          # one module
pytest tests/steps/caption_bbox/test_step.py::test_name # one test
python tests/run_pytest.py        # pytest wrapper that falls back to .venv site-packages
npm run test:ui                   # JS UI tests (node --test + jsdom)
```

Omitting `--output` defaults output to `outputs/<input-folder-name>/`. Re-running skips steps
already recorded in `outputs/<name>/.plk_state.json`; `--force` reruns everything.

## Environment

- Dependencies live under `requirements/`: `base.txt` is the cross-platform core/minimum
  (root `requirements.txt` is a shim that pulls it in); `seedvr2.txt` plus
  `seedvr2-{windows,linux}.txt` add the optional SeedVR2 upscaling runtime and OS-specific
  GPU acceleration extras. **Do not reinstall the runtime in a sandbox** — if `.venv/` is
  present, keep it intact. `tests/run_pytest.py` exists precisely to borrow that venv's
  site-packages when the active interpreter lacks pytest.
- SeedVR2 upscaling (`upscale_model: seedvr2`) is optional and lives in the
  `third_party/seedvr2` git submodule. It is invoked as an isolated worker subprocess
  (`steps/upscale/seedvr2_worker.py`), never imported into the main process. When the
  submodule/models are absent, Step 3 skips with a report reason rather than falling back.

## Architecture

The pipeline is **config-driven**: a project YAML lists ordered steps; the orchestrator looks
each step up in registries and dispatches. Adding a step touches several registries (see below),
not a single switch.

**Flow:** `cli/` (Click commands) -> loads `ProjectConfig` (`project/project_registry.py`)
-> `pipeline.run_all(RunConfig)` delegates to `pipeline/execution/`, which iterates
`project.pipeline` and skips done steps via `utils/state.RunState` (`.plk_state.json`) ->
for each step calls `STEP_INVOKE_MAP[step.type]` in `invoke/` → the adapter imports the
matching named `steps/*/` module and calls its `run()`. The original dataset is never mutated;
only `output_dir/dataset/` is. The UI's `runner/executor.py` coordinates typed requests from
`runner/run_request.py` with job hooks from `runner/execution_hooks.py`; `runner/manager.py`
only manages job lifecycle and thread error handling.

**Pipeline stages** (named packages, each `step.py` + helpers): `import_step` (ImportStep),
`quality_gate` (QualityGateStep), `curate` (CurateStep), `upscale` (UpscaleStep, optional),
`caption_bbox` (CaptionBboxStep), `vae_gate` (VaeGateStep), `audit` (AuditStep),
`bucket_pools_check` (BucketPoolsCheckStep), and `export_step` (ExportStep, optional). The
canonical order and direct dependencies live in `STEP_DEFINITIONS`.

**Step/substep registries** — the single source of truth is
`prepare_lora_kit_pipeline/configuration.py` plus
`prepare_lora_kit/project/pipeline/substeps.py`. Key tables: `STEP_DEFINITIONS`
and `SUBSTEP_REGISTRY`; callers should use the registry helper functions instead
of importing derived step maps. Ordering and direct
prerequisites are validated at config load; duplicate step types are rejected; legacy configs
missing `ImportStep` get it inserted in memory.

**Config models** are split deliberately:
- `prepare_lora_kit_pipeline/configs/*_config.py` — runtime dataclasses passed to step `run()`s.
- `project/config_schema/` — UI-facing field schemas (`steps/*.py`) for the mid-run step-config
  strip and override handling.
- Dataset-specific model and bucket choices live in step configs such as `VaeGateStep`,
  `AuditStep`, and `BucketPoolsCheckStep`.

**Configs on disk:** project presets in `configs/projects/`, caption prompts in
`configs/caption_prompts/`.

**UI** (`prepare_lora_kit_ui/`): `bridge.py` is the synchronous pywebview API object
(`window.pywebview.api`); `runner/` manages background jobs and pending interaction requests
(source review, VAE review, bbox annotation, curate confirmation). The frontend is plain ES
modules under `static/` (no bundler; `index.html` loads them directly). `e2e/` provides mock
fixtures for `--mock`.

## Conventions

- Keep files focused and small — aim for ≤500 lines. Before writing a file, check whether its
  use-case actually bundles multiple distinct sub-use-cases (or concerns); if so, split it into
  separate, single-responsibility files rather than growing one large file.
- Name step classes with the `*Step` suffix; keep step code in named `steps/<domain>/` packages.
- Tests mock all ML-heavy work (model loading, captioning, upscaling, VAE) and use
  `tmp_path`/`monkeypatch` — never touch real datasets or model caches. Add/update tests when
  changing config parsing, pipeline ordering, CLI behavior, or UI bridge payloads.
- Keep `prepare_lora_kit_ui/static/core/api.js` JSDoc in sync with
  `prepare_lora_kit_ui/bridge.py` whenever bridge payloads or frontend call sites change.
- Commits use conventional prefixes (`feat:`, `fix:`, `refactor:`) with an imperative summary.
- UI visual rules (the `nf-*` component kit, design tokens, gold-glow transition) are documented
  in `docs/ui-design.md`; `docs/core.md` describes the step/substep run model.
- `docs/caption-step.md` documents the `CaptionBboxStep` architecture (layering, VLM runtime,
  resume semantics, prompt sources, UI plumbing) — read it before changing `steps/caption_bbox/`.

## Adding a pipeline step

1. Add a runtime config dataclass in `prepare_lora_kit_pipeline/configs/`.
2. Add a UI field schema in `project/config_schema/steps/`.
3. Register the step in `STEP_DEFINITIONS` with its order, prerequisites, and
   optional/resume flags (`prepare_lora_kit_pipeline/configuration.py`).
4. Implement the step under `steps/<name>/step.py` with a `run()` entry point.
5. Add an invoke adapter module under `invoke/` + its `STEP_INVOKE_MAP` entry in `invoke/__init__.py`.
