# How bbox and caption are coupled

Part of the [Caption Step reference](README.md).

Boxes are not a separate output — they feed the caption prompt. Each annotation is
turned into prose by `steps/caption_bbox/prompts.py::describe_box_position(x1, y1, x2, y2)`
("in the upper-left", "a small element on the right"), combined with its label, and
injected into the `{bbox_annotations}` placeholder of the full-image prompt.

Separately, each drawn region can be captioned **on its own** in the UI, producing
an independent training pair: a crop PNG plus its caption `.txt`. So bbox work
yields both prompt context for the source image and extra dataset items.

**Region captions describe the crop only — never the full scene.** The idea:
the image is split into parts (bboxes), each bbox gets a small description of the
thing the VLM sees inside it, and those descriptions (including the user's manual
edits) later ground the full-image caption via `{bbox_annotations}`.
`CaptionRuntime.caption_region` therefore always sends the **crop** to the model
with a natural-phrase instruction (`prompts.build_region_prompt`). The normalized
box (threaded through `regions.make_region_captioner` →
`_region_caption_fn(crop, source_path, box=…)`) contributes only an **origin
hint** — "a cropped detail taken from `<position>` of a larger image" — to help
with partial/ambiguous objects on prompt-capable models. A custom `region_prompt`
may use the `{region_position}` placeholder (empty when the origin is unknown).

Human region labels are treated as ground truth downstream — see
[Region labels are enforced, not requested](prompts.md#region-labels-are-enforced-not-requested).
