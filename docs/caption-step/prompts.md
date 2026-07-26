# Prompts

Part of the [Caption Step reference](README.md).

Built-in templates live in `prepare_lora_kit/steps/caption_bbox/prompts.py`: a concept variant
(when `concept_token` is set), a style variant (when it is not), and a region
prompt. `default_prompt_text(kind)` is the single source of truth.

The user library is one YAML per prompt at
`configs/caption_prompts/<kind>__<slug>.yaml`, managed by
`caption_prompts/prompt_registry.py`. Kinds are `full_image` and `region`. The
`"Default"` entry is **virtual** — synthesized from `default_prompt_text`,
read-only, and cannot be saved or deleted. The directory is created on first save.

The selected text is stored on the project as `CaptionBboxConfig.caption_prompt`
and `region_prompt`; blank means use the built-in. Templating is plain replacement,
**not** `str.format`, so stray braces in prompts or captions are safe:

```python
def apply_prompt_placeholders(template, annotation_text, concept_token):
    return template.replace("{bbox_annotations}", annotation_text) \
                   .replace("{concept_token}", concept_token or "")
```

UI CRUD is exposed via `prepare_lora_kit_ui/bridge.py` as `list_caption_prompts`,
`save_caption_prompt` and `delete_caption_prompt`.

## Domain brief

`CaptionBboxConfig.domain_brief` is free-form prose describing what the dataset actually
depicts — vocabulary, what will appear, names never to use. `prompts.apply_domain_brief`
prepends it, marked authoritative, to **every** prompt that names or describes anything:
observe, compose, the single-pass full-image prompt, and the region prompt. It is
deliberately *not* a `{...}` placeholder, so it reaches user-authored library prompts too
without them opting in.

This is the only lever that supplies knowledge the model lacks. Abstention (see below)
stops a model outside its domain from asserting a wrong name; only the brief lets it
produce the right one. `caption_model.domain_brief` in the report records whether one was
in use (a bool, not the text).

It is a plain `_textarea` field, **not** `_prompt`: it is not a reusable prompt template
and must not be saved into the caption prompt library.

## Abstention

A VLM given only "state a fact" or "not visible" has no way to say *"present, but I don't
know what it is"* — so it names the nearest familiar thing with full confidence, and that
wrong noun then propagates as a fact. Every prompt therefore offers a third route: when
something is present but cannot be confidently named, describe its visible appearance
instead of naming it. The observe pass marks such lines with `?`, and compose is told to
keep the description, drop the marker, and never invent a name (the explanation is
appended only when the facts actually contain a `?`).

For LoRA training an appearance-level description is worth more than a confident wrong
noun — the text encoder grounds on what is described either way, and a wrong name poisons
the concept.

## Region labels are enforced, not requested

Both compose grounding paths declare human region labels ground truth and forbid renaming
them. `validation.enforce_region_labels` is the check behind that instruction: a label the
caption never mentions is appended via the same additive `gap_fill.merge_missing_phrases`
used by the gap pass. `_label_text` strips the concept token from a label first — a region
captioned in the UI carries the token on its own crop sidecar, and it belongs once, at the
head of the caption.

The check is deliberately **reluctant**, and this is the part to preserve when touching it:

- "Mentioned" is `caption_text.mentions` — does the caption name the label's **head noun**
  (`"a chipped enamel mug with a blue rim"` → `mug`) — *not* `covered`, which demands every
  content word. Compose is asked to weave labels in naturally, so it drops modifiers; the
  strict test read every paraphrase as a miss and re-appended the full label, producing
  captions that described the same region twice — vague prose first, the precise label
  tacked on the end. A paraphrase is a better caption than a duplicate.
- A label longer than `_MAX_ENFORCED_WORDS` (6 content words) is **never** appended, only
  reported. At that length it is a description in its own right, and appending it competes
  with the caption rather than repairing it.
- `gap_fill.needs_gap_pass` uses the same `mentions` test for its `missing_label` trigger,
  so the gate never spends a pass chasing a label enforcement would decline to append.
