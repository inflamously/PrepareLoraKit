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

The real resume lives in `_resolve_pending()`. Pending is the union of two sets
(or every image when `overwrite`):

1. images lacking a `.txt` — the plain resume set;
2. images the caption verifier judged `generic` or `wrong` and which have not
   been re-captioned since, read from `reports/caption_verdicts.json`.

If nothing is pending, the VLM is never loaded at all and the report is rebuilt
from the captions already on disk.

The second set is what makes a bad caption fixable. Without it, a verified
dataset has nothing pending — every image has a `.txt` — so the only way back
into the workspace would be `--force`, which re-captions everything and
invalidates VaeGate → Audit → Buckets → Export for the sake of one caption.

Two consequences worth knowing:

- **A resume run loads the VLM whenever anything is flagged**, and the load
  happens in `prepare_runtime()` *before* the modal opens. Re-running to fix
  three images means waiting out the model load first. Deferring it is not a
  small change: the region-captioner closure needs the runtime *during* the
  modal, not after it.
- A flagged image is reported to the workspace as **`done: false`** even though
  it has a caption. `batch.js::effectiveSkipped` submits `skipped: true` for an
  untouched *done* image, which would make phase B keep the very caption the
  reopen exists to replace.

Re-captioning an image marks its ledger entry `resolved`, so it drops out of the
pending set and its thumbnail goes neutral. An explicit "Skip image" does not:
the fix is merely deferred, and the image comes back next run.

`--force` reaches the adapter as `overwrite=True`, and
`resolve_force_invalidated_steps()` also resets this step and everything
downstream in `.plk_state.json`.
