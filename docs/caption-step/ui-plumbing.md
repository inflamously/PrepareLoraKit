# UI plumbing

Part of the [Caption Step reference](README.md).

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
