# CaptionVerifierStep

Optional step that answers one question per caption: **does the text encoder a LoRA will train
against actually know these words?**

`CaptionBboxStep` produces captions, but nothing downstream checks whether their terms mean
anything to the model. This step renders each caption with a text-to-image model — from the
caption text alone, never from the photo — and puts that render beside the real image, so a term
falls into one of three buckets:

| verdict | what you saw | what to do |
|---|---|---|
| `correct` | the feature renders | the encoder knows the term — keep it |
| `generic` | something plausible but unspecific | weak embedding — replace with a plain geometric description |
| `wrong` | a different concept entirely | the term is mis-bound — remove it, it is actively harmful |

Verdicts land in `reports/CaptionVerifierStep_report.json`; edited captions are written back to
`dataset/<stem>.txt`.

## Where it sits

`order=5`, immediately after `CaptionBboxStep` and before `VaeGateStep`. It is `optional=True`
(remove it from a project's pipeline to skip it entirely) and `resume_aware=True`, so a plain
re-run re-opens the review instead of reporting "already done" — otherwise the only way back in
would be `--force`, which would also invalidate VaeGate → Audit → Buckets → Export.

## Files

| file | role |
|---|---|
| `steps/caption_verifier/catalog.py` | Model catalog: ids, families, pipeline classes, sizing estimates, `auto_select` ladder. Torch-free. |
| `steps/caption_verifier/plan.py` | Pure VRAM planner: config + environment → `GenerationPlan`. No torch, no GPU. |
| `steps/caption_verifier/loader.py` | All diffusers imports. Pipeline-class resolution, quantization, placement, memory savers. |
| `steps/caption_verifier/t2i.py` | `T2IRuntime`: module-level cache + `threading.Lock`, lazy load, seeds, truncation detection, teardown. |
| `steps/caption_verifier/generation.py` | The `(prompt, options) -> dict` closure the UI's bridge RPC lands on. Owns preview filenames. |
| `steps/caption_verifier/captions.py` | Caption discovery and atomic write-back with path containment. |
| `steps/caption_verifier/reports.py` | Report assembly; every branch emits the same key set. |
| `steps/caption_verifier/step.py` | `run()` orchestration. |

UI: `prepare_lora_kit_ui/runner/caption_verify_interaction.py` (provider mixin),
`bridge.generate_caption_preview`, and `static/steps/caption_verify/`.

### Review modal

Three regions, one job each (`static/steps/caption_verify/components/`):

| region | file | holds |
|---|---|---|
| editor (left) | `editor.js` | the caption under test — the only editable copy — its char/token counts, and the one verdict control |
| preview (right) | `preview.js` | source vs render, the render settings strip, Render/Re-roll, and the notices (stale, truncated, error, live model status) |
| filmstrip (footer) | `strip.js` | navigation only: one tile per image, verdict dot, edited marker |

Shortcuts: `1`/`2`/`3` judge the selected image, `←`/`→` move through the strip
(all four ignored while the caption box has focus), `Ctrl`/`Cmd`+`Enter` renders
from anywhere in the modal. A tile's verdict dot stays neutral until that image
is actually judged — every item starts on the `correct` default, so a coloured
dot everywhere would read as "all approved" before the review began.

## Threading

Two threads meet here, and it drives most of the design:

```
pipeline thread                      pywebview RPC thread (one per bridge call)
step.run()
  interaction.caption_verify(items, generator=…)
    job.request_input("caption_verify", …)
      ↓ BLOCKS on a threading.Condition     user clicks Render
                                              bridge.generate_caption_preview(…)
                                                provider._generate_lock (non-blocking)
                                                  T2IRuntime.generate()  ← its own lock
      ↑ wakes on submit_input              user clicks Continue
  apply_caption_edits() → <stem>.txt
```

pywebview dispatches every bridge call on its own thread, so the frontend's 800 ms `pollJob`
never queues behind a 30-second render. That fact is what makes on-demand rendering viable.

Three locks, each with a distinct job:

- `T2IRuntime._lock` wraps the whole of `generate()`, load included. Two quick clicks must never
  enter the same CUDA pipeline together.
- `provider._verify_lock` guards a few fields and is **never** held across a render — holding it
  for 30 seconds would block `caption_verify`'s teardown and every cancel path.
- `provider._generate_lock` is held for the whole render and acquired **non-blocking**: a second
  concurrent request fails fast rather than parking a thread and then drawing a caption the user
  has already changed.

## Models and VRAM

`auto_select` ladder — no CUDA → SD 1.5 (CPU), ≤16 GB → SDXL, above → FLUX.2 klein.

Krea 2 is selectable but **never** an Auto pick: `Krea2Pipeline` is absent from diffusers 0.38,
so auto-selecting it would hand a load failure to a machine that is otherwise fine. A missing
pipeline class becomes an actionable "needs diffusers >= X" message, not a traceback.

`resolve_plan` budgets from **free** VRAM (`min(total*0.85, free-1)`), not total — that is what
lets the step run in the same process right after `CaptionBboxStep`. Quantization goes through
diffusers' `PipelineQuantizationConfig`, which applies the right backend per named component
(diffusers' `BitsAndBytesConfig` for the denoiser, transformers' for the text encoder).

One hard invariant, enforced by a parametrized test over every model × tier: **never emit
`("4bit", "sequential")`**. bitsandbytes 4-bit weights cannot be moved back to CPU, so accelerate's
sequential offload cannot drive them; the planner keeps the offload and drops the quantization.

FLUX.2 klein is a 9B transformer plus a Qwen3 text encoder. At nf4 with
`enable_model_cpu_offload()` only one submodel is resident at a time, which is what makes it fit
a 16 GB card. Never call `.to(device)` once offload hooks are installed — `_apply_placement`
keeps those branches mutually exclusive.

## Artifacts

Renders go to `reports/CaptionVerifierStep_previews/<stem>_<hash>/gen_<seed>_<nnn>.png`.

Two rules that look like details and are not:

- **Never inside `dataset/`.** `iter_images` recurses, so a probe render there would be picked up
  by AuditStep, BucketPoolsCheckStep and ExportStep as if a human had curated it.
- **A fresh filename per render.** The UI media endpoint sends
  `Cache-Control: private, max-age=86400`, so a re-roll written over the same path would be served
  from the browser cache without revalidation — silently showing the previous image.

## Caption write-back

The only step that lets a human free-type directly into training data, so:

- Writes are atomic (`tmp` + `os.replace` in the same directory). The temp suffix `.plk_tmp` is
  ignored by both `audit/checks.collect_stems` and `iter_images` if one ever leaks.
- Every submitted path is resolved and checked against the dataset root — the keys come over the
  bridge from JS and are untrusted. `plk_bbox__*` region sidecars are filtered twice.
- Empty captions are rejected, not written: an empty `.txt` makes AuditStep flag the image while
  ExportStep still ships it.
- Originals are backed up once to `CaptionVerifierStep_previews/captions_before/`.
- Text is stored **as typed** apart from `.strip()`. The trigger token is not re-injected and
  captions are not re-normalized — removing a term the encoder mis-binds is the entire point.

## Failure behaviour

`run()` never raises except `CancelledRun` (the VaeGateStep contract). Everything else becomes a
report with a reason. `skipped: true` only when the step produced nothing at all — a run with some
renders or verdicts is a partial success carrying `failures`.

Headless runs skip cleanly: `CliInteractionProvider` deliberately has no `caption_verify`, and the
step probes with `getattr`.

## Caveats worth stating

- **The premise is a heuristic.** SDXL and FLUX are joint text-image models; a term can live in
  the encoder yet not survive the denoiser's prior, and every render depends on the seed. Re-roll
  before trusting a verdict.
- **The truncation flag is the most reliable signal.** SD 1.5 and SDXL cut at 77 tokens, so a term
  past that position never reached the model at all and a bad render says nothing about it.
  FLUX.2 klein carries 512.
- **The step-config modal is opt-in.** It only appears when "Pause to edit step config" is ticked,
  so the dataclass defaults must be usable on their own.
