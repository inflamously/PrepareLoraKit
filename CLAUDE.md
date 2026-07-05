# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PrepareLoraKit is a Python 3.10+ CLI (`plk`) that prepares image datasets for LoRA-style
training of Flux and similar diffusion models. It takes an untouched source folder, builds a
separate working dataset under `outputs/<name>/dataset/`, runs an ordered pipeline of
preparation steps, and emits per-step JSON reports plus an ai-toolkit-compatible
`run_config.yaml` (the main training handoff artifact). A pywebview desktop UI wraps the same
pipeline.

## Commands

```bash
python main.py <cmd>          # run CLI from the checkout (or `plk <cmd>` after `pip install -e .`)
python main.py run -i /path/to/images -p example -t my_trigger   # full pipeline
python main.py step -s CaptionStep -p example -i ... -o ... -t ... # single step (alias s0..s8 also work)
python main.py ui                 # launch the desktop webview UI (--mock <STEP> for fixture data)
python main.py projects           # list configs/projects/
python main.py networks           # list configs/networks/

pytest                            # full Python test suite
pytest tests/project/test_config.py          # one module
pytest tests/steps/s5_caption/test_step.py::test_name   # one test
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
  (`steps/s3_upscale/seedvr2_worker.py`), never imported into the main process. When the
  submodule/models are absent, Step 3 skips with a report reason rather than falling back.

## Architecture

The pipeline is **config-driven**: a project YAML lists ordered steps; the orchestrator looks
each step up in registries and dispatches. Adding a step touches several registries (see below),
not a single switch.

**Flow:** `cli/` (Click commands) → loads `ProjectConfig` (`project/registry.py`) and a
`NetworkProfile` (`networks/registry.py`) → `pipeline.run_all(RunConfig)` iterates
`project.pipeline`, skipping done steps via `utils/state.RunState` (`.plk_state.json`) →
for each step calls `STEP_INVOKE_MAP[step.type]` in `invoke/` → the adapter imports the
matching `steps/sN_*/` module and calls its `run()`. The original dataset is never mutated;
only `output_dir/dataset/` is. The UI runs the *same* pipeline through `ui/runner/` +
`ui/bridge.py` instead of the CLI.

**Pipeline stages** (`steps/sN_*/`, each `step.py` + helpers): `s0_import` (ImportStep — the
only image copy), `s1_source` (QualityGateStep), `s2_curate` (CurateStep — dedupe + CLIP
coverage), `s3_upscale` (UpscaleStep, optional), `s5_caption` (CaptionStep — bbox UI + Qwen
VL), `s4_vae_gate` (VaeGateStep), `s6_audit` (AuditStep), `s7_config` (ConfigGenStep — builds
`run_config.yaml`), `s8_bucket` (BucketDryRunStep), `s9_export` (ExportStep, optional/opt-in —
copies the finalized image + `.txt` pairs to a sibling `<input>_export/` folder after a diff
pre-step; never mutates the source or working dataset). Note the directory number is *not* the
pipeline position (vae_gate `s4` runs *after* caption `s5`); the canonical order lives in
`STEP_ORDER`.

**Step/substep registries** — the single source of truth is
`project/pipeline/{steps,substeps}.py`; `project/steps.py` is a thin re-export shim, so import
from either. Key tables: `STEP_TYPE_MAP`, `STEP_ORDER`, `STEP_PREREQUISITES`,
`OPTIONAL_STEP_TYPES`, `SUBSTEP_REGISTRY`. Ordering is validated at config load (each step
requires its predecessor earlier; duplicates rejected; legacy configs missing `ImportStep`
get it inserted in memory).

**Config models** are split deliberately:
- `project/configs/*_config.py` — runtime dataclasses passed to step `run()`s.
- `project/config_schema/` — UI-facing field schemas (`steps/*.py`) for the mid-run step-config
  strip and override handling.
- `networks/` — `NetworkProfile` describes the base model, VAE id, buckets, LR/rank ranges, and
  the ai-toolkit `model`/`network`/`train`/`save`/`sample` template blocks used by ConfigGenStep.
  `vae_model_id` (consumed by the VAE gate, `steps/s4_vae_gate/vae.py`) accepts three forms: a
  diffusers repo id or local dir (loaded via `from_pretrained(subfolder="vae")` — only the `vae/`
  subfolder is fetched, not the full model); a single-file checkpoint path/URL ending in
  `.safetensors`/`.ckpt`/`.pt`/`.bin` (e.g. ComfyUI `ae.safetensors`, `sdxl_vae.safetensors`,
  loaded via `from_single_file`); or `repo_id::path/in/repo.safetensors` to grab one file from an
  HF repo. Optional `vae_config_id` points the single-file loader at a base repo's `vae/` config
  when diffusers can't infer it from the checkpoint keys.

**Configs on disk:** project presets in `configs/projects/`, network profiles in
`configs/networks/`, caption prompts in `configs/caption_prompts/`.

**UI** (`ui/`): `bridge.py` is the synchronous pywebview API object (`window.pywebview.api`);
`ui/runner/` manages background jobs and pending interaction requests (source review, VAE
review, bbox annotation, curate confirmation). The frontend is plain ES modules under
`ui/static/` (no bundler — `index.html` loads them directly). `ui/e2e/` provides mock fixtures
for `--mock`.

## Conventions

- Keep files focused and small — aim for ≤500 lines. Before writing a file, check whether its
  use-case actually bundles multiple distinct sub-use-cases (or concerns); if so, split it into
  separate, single-responsibility files rather than growing one large file.
- Name step classes with the `*Step` suffix; keep step code in its numbered `steps/sN_*/` package.
- Tests mock all ML-heavy work (model loading, captioning, upscaling, VAE) and use
  `tmp_path`/`monkeypatch` — never touch real datasets or model caches. Add/update tests when
  changing config parsing, pipeline ordering, CLI behavior, or UI bridge payloads.
- Keep `ui/static/core/api.js` JSDoc in sync with `ui/bridge.py` whenever bridge payloads or
  frontend call sites change.
- Commits use conventional prefixes (`feat:`, `fix:`, `refactor:`) with an imperative summary.
- UI visual rules (the `nf-*` component kit, design tokens, gold-glow transition) are documented
  in `docs/ui-design.md`; `docs/core.md` describes the step/substep run model.

## Adding a pipeline step

1. Add a runtime config dataclass in `project/configs/`.
2. Add a UI field schema in `project/config_schema/steps/`.
3. Register in `STEP_TYPE_MAP` and add ordering to `STEP_PREREQUISITES`
   (`project/pipeline/steps.py`).
4. Implement the step under `steps/sN_<name>/step.py` with a `run()` entry point.
5. Add an invoke adapter module under `invoke/` + its `STEP_INVOKE_MAP` entry in `invoke/__init__.py`.
