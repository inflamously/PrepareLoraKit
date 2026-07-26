# Caption strategy (grounded vs single)

Part of the [Caption Step reference](README.md).

`CaptionBboxConfig.caption_strategy` selects how the **full-image** caption is produced;
it threads through the adapter → `step.run()` → `RealCaptionStep` → `CaptionRuntime`.

- **`grounded`** (default) — a staged pipeline in `grounded.py::generate_grounded_caption`,
  reusing the *one* already-loaded VLM (no extra model, no extra dependency). Only COMPOSE
  always runs; the other two stages are conditional, because on a VLM the cost of a stage
  is dominated by re-encoding the image, so skipping a stage is the only real saving:
  1. **OBSERVE** — list only-visible facts under fixed headings
     (`prompts.build_observe_prompt`); this is where accuracy is won. Gets a larger token
     budget (`_OBSERVE_MIN_TOKENS = 320`). **Skipped** when
     `grounded._annotations_suffice` holds — ≥2 labelled regions, or one label of ≥4
     content words. Region labels are human-authored and hand-editable, so where they
     exist they are better grounding than the model's own observations.
  2. **COMPOSE** — write one fluent caption from those facts + bbox placement prose
     (`prompts.build_compose_prompt`). A custom `caption_prompt` overrides **only** this
     stage; observed facts, when there are any, are prepended as grounding context.

     An **empty `facts`** is the signal that OBSERVE was skipped: the prompt then swaps
     its grounding section (`prompts._FACTS_SECTION_ANNOTATED`) to declare the labels
     authoritative and instruct the model to read the attributes labels cannot supply —
     setting, framing, lighting, palette, medium — off the image directly. That works
     because COMPOSE is image-conditioned too, not a text-only rewrite.
  3. **GAP-FILL** — conditional and additive. `gap_fill.needs_gap_pass` gates it on cheap
     text signals (`short_caption` under 20 words, `missing_label` when a region label is
     absent from the draft, `low_information` on banned filler vocabulary); a clean draft
     skips the pass and the third image encode entirely. When it does run,
     `prompts.build_gap_prompt` asks **only** for a list of omitted elements — at most 3
     short noun phrases, or `NONE` — and `gap_fill.merge_missing_phrases` appends the ones
     not already covered (`_GAP_MAX_TOKENS = 48`).

  Stage 3 asks for a phrase list rather than a corrected caption **by design**: an output
  format that is a full caption lets the model paraphrase human-authored region labels and
  drop detail, and no prompt wording prevents that. Emitting a delta and merging in Python
  makes the pass additive by construction.

  Each stage degrades gracefully (`_degenerate` → fall back to the prior stage / a plain
  single pass), so grounded never returns worse than single. Per-stage progress is emitted
  through the existing `caption_status_callback` (phase stays `captioning`, message cycles
  `observing → composing`, plus `verifying` only when the gap pass actually runs).

- **`single`** — the original one-shot generation (`build_full_image_prompt` → one
  `generate()`). This is also the automatic fallback for **classic `image-to-text`**
  models: they cannot follow multi-turn instructions, so `caption_image` routes them to the
  single path + `_compose_classic_caption` regardless of the configured strategy. The gate
  is `caption_strategy == "grounded" and CaptionRuntime.supports_prompt`.

Because both conditional stages depend on per-image content, the only record of what a run
actually cost is `caption_model.passes` — a `{stage: count}` tally accumulated by
`CaptionRuntime.note_pass` over the whole step (`observe`, `compose`, `compose_fallback`,
`gap`). A 40-image run showing `{"compose": 40, "observe": 12, "gap": 7}` did 59 image
encodes where the old unconditional 3-pass pipeline would have done 120.

The chosen strategy is recorded in the report under `caption_model.caption_strategy`. The
`--mock` runtime overrides `caption_full_image` directly and never constructs a
`CaptionRuntime`, so mock output is unaffected by this setting.
