# Complexity Technical Debt

Audited on 2026-06-24. This list highlights files that exceed roughly 300 lines of code, carry too many responsibilities in one place, or are otherwise harder than necessary to read and modify. Checked-in third-party code is called out separately from first-party refactor candidates.

| Filepath | Description |
| --- | --- |
| `third_party/seedvr2/` | Large checked-in third-party integration; many files exceed 800-1700 LoC and cover inference, model loading, generation phases, memory management, optimization, and VAE/DiT model internals, so it should be tracked separately from first-party cleanup unless maintained locally. |
| `prepare_lora_kit/ui/static/core/app-kit.css` | 809 LoC; combines app shell, title bar, panels, fields, buttons, pills, pipeline steps, console, status bar, toolbar, project cards, metrics, key-value rows, and responsive rules in one stylesheet. |
| `prepare_lora_kit/invoke.py` | 515 LoC; mixes step invoke adapters, runtime bridge kwargs, step map registration, working dataset validation, and mock implementations for curate, embeddings, VAE gate, and captions. |
| `tests/ui/test_runner.py` | 477 LoC; broad UI runner suite covers selection validation, payloads, run sequencing, static media, interaction payloads, logging, rich console behavior, cancellation, and status updates. |
| `prepare_lora_kit/steps/s3_upscale/step.py` | 399 LoC; one module handles candidate selection, model normalization, SeedVR2 resolution, fallback behavior, batch/single-image processing, hallucination rejection, temp cleanup, passthrough, and report writing. |
| `tests/project/test_config.py` | 379 LoC; covers YAML parsing, default project creation, legacy migrations, step ordering, optional upscale behavior, SeedVR2 catalog/config validation, and UI payload metadata. |
| `tests/ui/test_dev_fixture.py` | 374 LoC; mixes fixture API tests, dataset generation, mock project bridge behavior, curate job execution, coverage plotting, quality gate flow, VAE decisions, and YAML compatibility. |
| `prepare_lora_kit/ui/nflamously.css` | 343 LoC; combines design tokens/theme variables, base document styles, scrollbars, and reusable glass/eyebrow utilities. |
| `prepare_lora_kit/steps/s5_caption/annotate.py` | 313 LoC; tkinter annotation UI keeps window construction, canvas drawing, box hit-testing, label editing, region captioning, skip/done state, normalization, and fallback wrapper in one class/module. |
| `prepare_lora_kit/ui/static/core/foundation.css` | 310 LoC; combines CSS variables/tokens, global element resets, typography defaults, select/button/input primitives, panels/modals, and base component styling. |
| `prepare_lora_kit/ui/runner/manager.py` | 302 LoC; `JobManager` owns job lifecycle, cancellation, log redirection, request parsing, project/network loading, substep resolution, prerequisite validation, pipeline execution, interaction dispatch, and result payloads. |
| `prepare_lora_kit/project/steps.py` | 276 LoC; below threshold but high intent density: canonical step registry, prerequisites, substep definitions, legacy/default normalization, YAML validation, UI payload construction, state satisfaction, and alias generation. |
