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

## This folder

| Doc | Covers |
|---|---|
| [architecture.md](architecture.md) | Layering diagram, what each layer owns, the file map. |
| [substeps.md](substeps.md) | The three substeps, what disabling each one does, selection flow. |
| [run-flow.md](run-flow.md) | Step-by-step control flow of `run()`, and resume semantics. |
| [bbox-regions.md](bbox-regions.md) | How boxes feed the caption prompt, and why region captions describe the crop only. |
| [vlm-runtime.md](vlm-runtime.md) | `vlm.py`: model loading, adapters, caching, quantization, OOM defense. |
| [caption-strategy.md](caption-strategy.md) | `grounded` (observe → compose → gap-fill) vs `single`. |
| [prompts.md](prompts.md) | Built-in templates, the user prompt library, domain brief, abstention, region-label enforcement. |
| [artifacts.md](artifacts.md) | Files written to disk and the report payload. |
| [ui-plumbing.md](ui-plumbing.md) | Lifecycle hooks, live caption status, interaction requests, frontend. |

## Known sharp edges

- `vlm.py` is ~600 lines, well over the ≤500-line convention in `CLAUDE.md`. It
  bundles model loading, quantization, device handling, prompt building and
  generation — see [`../complexity-technical-debt.md`](../complexity-technical-debt.md).

Resolved by the class refactor: the substep id list is no longer duplicated — every
consumer (`base.py`, `reports.py::substep_status`, the mock) reads it from
`SUBSTEP_REGISTRY` via `substep_ids_for("CaptionBboxStep")`. And the `--mock`
runtime is a `CaptionStep` subclass sharing the real orchestration instead of a
hand-maintained clone.
