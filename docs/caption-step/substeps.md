# Substeps

Part of the [Caption Step reference](README.md).

Registered in `prepare_lora_kit/project/pipeline/substeps.py`:

```python
"CaptionBboxStep": (
    SubstepDefinition("annotate_regions", "Annotate regions"),
    SubstepDefinition("caption_images", "Caption images"),
    SubstepDefinition("validate_captions", "Validate captions",
                      prerequisites=("caption_images",)),
),
```

All three are non-optional and enabled by default. What each toggle does when
**disabled**:

- `annotate_regions` — `gather_decisions` short-circuits to empty annotations for
  every image. The same happens automatically when `interaction is None`, i.e. on
  the CLI and in headless runs, so the step degrades to plain captioning.
- `caption_images` — `gather_decisions` returns `{}` and `resolve_decision`
  returns `None`. Existing `.txt` sidecars are preserved and the report is rebuilt
  from them. Bbox sidecars survive untouched.
- `validate_captions` — `validate_captions` and `render_spot_check` return empty.
  Declares a prerequisite on `caption_images`.

Selection flows `pipeline/execution/selection.py` → `engine._invoke_step` →
adapter `enabled_substeps` kwarg → `run()`, where it becomes the `enabled` set.
