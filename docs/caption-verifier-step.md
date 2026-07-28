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
| `steps/caption_verifier/load_status.py` | Live progress while the load blocks: heartbeat thread + tqdm tap. Torch-free. |
| `steps/caption_verifier/weights.py` | Turns those tqdm bars into weight bytes loaded, against the checkpoint's real size on disk. Torch-free, cache-only. |
| `steps/caption_verifier/runtime_env.py` | Everything the runtime says to torch: VRAM probe, CPU generator, hook freeing, cache release. |
| `steps/caption_verifier/t2i.py` | `T2IRuntime`: module-level cache + `threading.Lock`, lazy load, seeds, truncation detection, status, teardown. |
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
| editor (left) | `editor.js` | the live model status, the caption under test — the only editable copy — its char/token counts, and the one verdict control |
| preview (right) | `preview.js` | source vs render, the render settings strip, Render/Re-roll, and the notices about this render (stale, truncated, error) |
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

## The load is the wait

The first Render click of a run pays for the model load. For a 9B FLUX.2 klein at nf4 that is
minutes — first-run download, shard reads, quantization, offload wiring — inside one
`loader.load_pipeline` call that returns nothing until it is finished. The bridge call the modal is
awaiting is blocked for all of it, so the **job poll is the only channel still speaking**.

Four things ride it (`T2IRuntime._set_status` → `job.set_caption_status` → `pollJob`):

| field | what it carries |
|---|---|
| `phase` | `resolving` → `loading` → `generating` → `ready`, or `failed` |
| `detail` | the current tqdm bar, e.g. `Loading checkpoint shards · 3/6` or `model-00002-of-00006.safetensors · 2.0 GB / 4.0 GB` |
| `progress` / `elapsed_s` | fraction for the bar, seconds for the clock |
| `weights_loaded_bytes` / `weights_total_bytes` | how much of the checkpoint is in, e.g. `Weights 6.2 / 9.4 GB · 66%` |

The weight pair comes from `weights.WeightProgress`, which converts the load's own tqdm bars into
bytes. **The total is exact** — the size on disk of the weight files this load reads, taken from the
Hugging Face cache, not from the `params_b` estimates in `catalog.py` (those are for picking a
quantization tier and are wrong by whatever the format and the quantization decided). The loaded
figure is component-granular: `Loading pipeline components...` says how many components are done, and
this turns each into its real size, because a VAE and a 9B transformer are one step of that bar
apiece and two orders of magnitude apart. Inside the big ones, `Loading checkpoint shards` refines it
further — which is exactly where the wait is.

`progress` is derived from the same pair whenever it is available. A raw tqdm fraction belongs to one
component, so a bar driven by it runs 0→100% once per component; measured against the whole
checkpoint it only ever moves forward. For the same reason the byte figure is high-watermarked.

Both fields are omitted (never zeroed) when the checkpoint cannot be measured: a single-file model
id, an unreadable cache, and the whole of a first-run download — during which nothing is loaded
because nothing has arrived yet, and the download's own byte counts are already on the `detail` line.
`WeightProgress` re-reads the cache on each tick until it succeeds, so the line appears by itself the
moment the files land. It never imports torch, diffusers or `huggingface_hub` at module scope, and it
never makes a Hub request — a network round trip on the heartbeat would buy a status line at the cost
of the thing it describes.

Components the loader passes as `None` (SD 1.5's `safety_checker`) are declared by
`loader.skipped_components`, the same function that builds the kwargs. diffusers drops them from
`init_dict`, which is both what it iterates and what this counts against, so a missing entry would
inflate the total and shift every position in it.

Every snapshot is rebuilt from scratch, so a `detail` from the load can never linger over a render.

`load_status.watch()` supplies the signals the load itself does not:

- a **heartbeat** (1 s, matched to the UI's 800 ms poll) that re-publishes the current phase with a
  fresh `elapsed_s`. Without it a slow load and a hung one are the same screen;
- a **tqdm tap**, since a tqdm bar is the only progress Hugging Face exposes. It patches
  `tqdm.std.tqdm.__init__`/`update`, **not** `tqdm.auto.tqdm`: diffusers, transformers and
  huggingface_hub each bound `tqdm.auto.tqdm` into their own module namespace at import time, so
  rebinding it now would reach none of them — but every one of those names is a subclass that
  inherits `update` and calls `super().__init__()`. The tap is restored in a `finally`, acquired
  non-blocking (a second tap skips rather than unpatching out of order), and every callback is
  swallowed: losing the detail line must never cost the load;
- a **weight tracker** (`weights=`), fed every bar the tap sees and sampled once per tick rather than
  per bar — diffusers advances a shard bar from a thread pool, hundreds of times a second, and the
  frontend reads 800 ms apart.

A load that raises publishes `failed` on the way out. The exception surfaces on the RPC thread as a
rejected promise, and nothing else would ever write the banner again — it would sit on "Loading…"
for the rest of the run.

Frontend: the status sits above the caption box (`components/editor.js`), not beside the Render
button that starts it — the preview pane is the only column that scrolls, so a status parked at the
bottom of its notices is below the fold on a short window, which is exactly where a ten-minute load
must not be. The placeholder says **"Loading model… 6m 12s"** while the phase is
`loading`, not "Rendering…" — the modal's own 1 s ticker retouches that label in place rather than
re-rendering the pane, which would otherwise re-parse both `<img>` tags several hundred times
across a ten-minute load.

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
