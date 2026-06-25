# Complexity Technical Debt

Audited on 2026-06-25. This list highlights files that exceed roughly 300 lines of code, carry too many responsibilities in one place, or are otherwise harder than necessary to read and modify. Checked-in third-party code is called out separately from first-party refactor candidates.

| Filepath | Description |
| --- | --- |
| `third_party/seedvr2/` | 25,814 LoC of checked-in third-party integration; large files cover inference CLI, model configuration/loading, generation phases, memory management, optimization, VAE/DiT internals, and image/video upscaling, so local changes should be tracked separately from first-party cleanup. |
| `prepare_lora_kit/ui/static/core/app-kit.css` | 809 LoC; combines app shell, title bar, panels, fields, buttons, pills, pipeline steps, console, status bar, toolbar, project cards, metrics, key-value rows, and responsive rules in one stylesheet. |
| `prepare_lora_kit/steps/s5_caption/vlm.py` | 585 LoC; owns Hugging Face model loading, quantization and dtype selection, CUDA/VRAM checks, image preprocessing, prompted and image-to-text generation adapters, caption composition, cache lifecycle, runtime status payloads, and public caption helpers. |
| `tests/ui/test_runner.py` | 518 LoC; broad UI runner suite covers selection validation, project payloads, run sequencing, static media serving, interaction payloads, log stream behavior, rich console capture, cancellation, job snapshots, and region caption cropping. |
| `prepare_lora_kit/invoke.py` | 518 LoC; mixes production step invoke adapters, step map registration, working dataset validation, runtime bridge kwargs, and deterministic mock implementations for curate, embeddings, VAE gate, and captions. |
| `prepare_lora_kit/steps/s3_upscale/step.py` | 399 LoC; one module handles candidate partitioning, model normalization, SeedVR2 resolution, fallback behavior, batch and single-image processing, hallucination rejection, temp cleanup, passthrough, and report writing. |
| `tests/project/test_config.py` | 381 LoC; covers project YAML parsing, default project generation, legacy migrations, step ordering, optional upscale behavior, SeedVR2 catalog/config validation, and UI payload metadata. |
| `tests/ui/test_dev_fixture.py` | 374 LoC; mixes fixture API tests, dataset generation, mock bridge bootstrap behavior, mock job execution, curate coverage plotting, quality gate flow, VAE decisions, and YAML compatibility. |
| `prepare_lora_kit/ui/nflamously.css` | 343 LoC; combines design tokens/theme variables, typography and spacing scales, base document styles, scrollbars, and reusable glass/eyebrow utilities. |
| `prepare_lora_kit/ui/static/core/foundation.css` | 310 LoC; combines CSS variables/tokens, global element resets, typography defaults, form/button primitives, panel/modal styling, and base component behavior. |
| `prepare_lora_kit/ui/runner/manager.py` | 304 LoC; `JobManager` owns job lifecycle, cancellation, log redirection, request parsing, project/network loading, substep resolution, prerequisite validation, pipeline execution, interaction dispatch, and result payloads. |
| `prepare_lora_kit/project/steps.py` | 276 LoC; below threshold but high intent density: canonical step registry, prerequisites, substep definitions, legacy/default normalization, YAML validation, UI payload construction, state satisfaction, and alias generation. |
| `prepare_lora_kit/steps/s3_upscale/seedvr2_worker.py` | 275 LoC; below threshold but high integration density: subprocess CLI request/response IO, dynamic SeedVR2 import, model download, per-item processing, full argument construction, device selection, model residency heuristics, and error normalization. |
