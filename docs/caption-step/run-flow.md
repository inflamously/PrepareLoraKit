# Control flow and resume semantics

Part of the [Caption Step reference](README.md).

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
