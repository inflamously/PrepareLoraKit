# Artifacts written

Part of the [Caption Step reference](README.md).

- `{stem}.txt` — the training caption, beside each image in the working dataset.
- `plk_bbox__{stem}__{NN}.png` + matching `.txt` — one independent training pair
  per drawn region.
- `plk_bbox__{stem}__boxes.json` — reload sidecar with normalized coordinates,
  labels and `crop_name`. Writing an empty list deletes the file.
- `outputs/<name>/reports/CaptionBboxStep_report.json` — the step report. When
  `report_path` is `None`, the same `CaptionBboxStep_report.json` name is used
  under `output_dir` (`reports.py::_REPORT_NAME`).
- `outputs/<name>/reports/caption_verdicts.json` — **read, and written only to
  retire an entry.** Owned by
  [CaptionVerifierStep](../caption-verifier-step.md); this step reads it to
  decide which captioned images to reopen, and flips `resolved` on each image it
  re-captions. Located from `_resolved_report_path(output_dir).parent`, never
  from `output_dir` — for this step `output_dir` is the working dataset, so
  deriving it there would put the two steps on different files.

The report payload (`reports.py::build_success_report`) carries `total`,
`captioned`, `caption_model`, `caption_status`, `skipped_annotation`,
`missing_token`, `short_captions`, `long_captions`, `spot_check_sample`, and a
`substeps` block recording which substeps were enabled. Inside `caption_model`:
`passes` (what each stage actually cost, see
[caption-strategy.md](caption-strategy.md)) and `domain_brief` (whether one was
set, see [prompts.md](prompts.md#domain-brief)).
