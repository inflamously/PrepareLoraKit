/**
 * @typedef {"queued" | "running" | "waiting_input" | "cancelling" | "completed" | "failed" | "cancelled"} JobStatus
 */

/**
 * One ordered unit inside a parent step, built by `substep_payloads` in
 * `prepare_lora_kit/project/pipeline/substeps.py`. Every substep the registry
 * defines for the parent is always present — `enabled` says whether it is on,
 * the list is never filtered.
 *
 * @typedef {Object} SubstepPayload
 * @property {string} id Registry id, unique within the parent step (e.g.
 *   `score_images`). The value `RunRequest.substeps[stepType]` carries and the
 *   key `state.selectedSubsteps` stores.
 * @property {string} label Human name from the substep registry, shown as the
 *   row title. The step list falls back to `id` if it is ever missing.
 * @property {boolean} enabled Config-level on/off from the project's
 *   `<slug>.yaml`, not a UI selection. `false` labels the row "Disabled", keeps
 *   the substep out of its parent's default selection, and stops it running.
 * @property {"pending" | "done" | "skipped"} status What this substep did on the
 *   last run. `pending` covers "never ran" — including substeps of a parent that
 *   is itself done, which a partial run leaves behind.
 * @property {string[]} prerequisites Sibling substep ids in the same parent that
 *   must run first (`review_decisions` requires `score_images`). Ordering
 *   metadata — the UI neither displays nor enforces it.
 * @property {boolean} optional Registry metadata, rendered as "- Optional" in
 *   the row. Display only, unlike {@link StepPayload}`.optional`: it drives no
 *   selection or run logic, `enabled` is what decides whether the substep runs.
 */

/**
 * Dataset precheck behind the soft step recommendation, computed on every
 * project load by `upscale_attention` in
 * `prepare_lora_kit_ui/runner/recommendations.py`. It scans the working dataset
 * (`<output_dir>/dataset`) when that exists, else the raw input folder.
 *
 * @typedef {Object} StepAttention
 * @property {boolean} recommended True when `undersized` or `jpeg` is non-zero.
 *   This, not the raw counts, is what sets `StepPayload.needs_attention`.
 * @property {number} undersized Images whose short side is <= the step's highlight threshold.
 * @property {number} jpeg JPEG-encoded images (compression artifacts).
 * @property {number} scanned How many images were scanned (capped at 5000, so on
 *   a bigger folder the counts describe a sample, not the whole dataset).
 */

/**
 * One pipeline step as the bridge sends it, built by `_step_payload` in
 * `prepare_lora_kit_ui/runner/payloads.py`. `ProjectPayload.steps` holds one per
 * configured step, in pipeline order.
 *
 * @typedef {Object} StepPayload
 * @property {string} type CamelCase step class name (e.g. `ImportStep`) — the id
 *   everything else keys off: `state.selectedSteps`, `RunRequest.steps`,
 *   run-state records, `reports/<type>_report.json`. Not the on-disk name: the
 *   project YAML file is named after the step's slug (`caption_bbox.yaml`).
 * @property {Record<string, unknown>} config The step's config dataclass from
 *   its `<slug>.yaml`, flattened to JSON (nested dataclasses become objects,
 *   `Path` values become strings). Shape varies per step type; only the step
 *   config modal reads it.
 * @property {"pending" | "done" | "skipped" | "stale"} status Persisted run-state
 *   status. `skipped` is a step that ran but whose own report said it did no work
 *   (an empty dataset, a disabled substep); it is still `done` for prerequisites
 *   and resume, so a plain re-run skips it until `force`. `stale` is a step whose
 *   run state claims a run whose `reports/<StepType>_report.json` is no longer on
 *   disk — the record outlived its evidence and the step wants re-running.
 *   `pending` also covers "no output dir resolved yet", where nothing has been
 *   read from disk at all.
 * @property {string} status_reason Why the step is not plainly done — the reason
 *   its report gave, or which report has gone missing. Empty string when the
 *   status speaks for itself.
 * @property {string[]} prerequisites Step types that must have run before this
 *   one, from `StepDefinition.prerequisites`. Checked against the persisted run
 *   state at run time (a `skipped` step satisfies them — run state records it as
 *   done); the step list only surfaces them as "Requires ..." and never blocks
 *   selection on them.
 * @property {boolean} optional Static `StepDefinition.optional` flag — today
 *   `UpscaleStep`, `CaptionVerifierStep` and `ExportStep`. It means opt-in, not
 *   unrunnable: no toolbar selection ever checks an optional step ("Select
 *   steps" and "Select pending tasks" both skip them, as does project load),
 *   the library card's completed check ignores them, and the step list leaves
 *   their badge blank while they are `pending`. Only a manual click runs one.
 * @property {SubstepPayload[]} substeps Every substep the registry defines for
 *   this step type, in canonical order. Empty for step types that have none.
 * @property {boolean} [needs_attention] Soft step-list recommendation. Only
 *   UpscaleStep ever carries it — for every other step type the key is absent
 *   rather than `false`, so test it as optional.
 * @property {StepAttention | null} [attention] Why the step is recommended.
 *   `null` when there was no readable dataset to scan, and absent alongside
 *   `needs_attention` for every step but UpscaleStep.
 */

/**
 * @typedef {Object} ProjectPayload
 * @property {string} name
 * @property {string | null} input_dir
 * @property {StepPayload[]} steps
 */

/**
 * @typedef {Object} ProjectLoadResult
 * @property {ProjectPayload} project
 * @property {string} project_name
 * @property {string | null} input_dir
 * @property {string | null} output_dir
 * @property {boolean} output_exists True when output_dir exists on disk.
 */

/**
 * @typedef {Object} RunRequest
 * @property {string} input_dir
 * @property {string | null} output_dir
 * @property {string} project
 * @property {string | null} token
 * @property {boolean} force Run active steps from the beginning instead of skipping completed steps.
 * @property {string | null} caption_model_id
 * @property {"auto" | "image-text-to-text" | "image-to-text"} caption_model_task
 * @property {string} caption_vram_mode
 * @property {boolean} [mock_runtime]
 * @property {"auto" | "pca" | "umap"} [mock_curate_coverage]
 * @property {string[]} steps Active step types in project order.
 * @property {Record<string, string[]>} substeps Config-enabled substeps for each active step.
 */

/**
 * @typedef {Object} BootstrapPayload
 * @property {string} project
 * @property {string} input_dir
 * @property {string} output_dir
 * @property {string[]} selected_steps
 * @property {boolean} force
 * @property {string} token
 * @property {boolean} mock_runtime
 * @property {"auto" | "pca" | "umap"} mock_curate_coverage
 */

/**
 * @typedef {Object} ImagePayload
 * @property {string} path
 * @property {string} name
 * @property {string} uri Full-resolution media URL (fallback / originals).
 * @property {string} [thumb_uri] Downscaled variant for grids and the caption thumbnail strip.
 * @property {string} [view_uri] Viewport-sized variant for detail panes and the annotation canvas.
 */

/**
 * @typedef {Object} SourceReviewItem
 * @property {string} path
 * @property {string} name
 * @property {string} uri
 * @property {string} [thumb_uri] Downscaled grid variant.
 * @property {string} [view_uri] Viewport-sized detail variant.
 * @property {Record<string, unknown>} scores
 * @property {number | null} quality
 * @property {boolean} auto_reject
 * @property {string[]} auto_reasons
 * @property {"keep" | "reject" | "flag"} initial_decision
 */

/**
 * @typedef {Object} VaeReviewViews
 * @property {ImagePayload} original
 * @property {ImagePayload} vae
 * @property {ImagePayload} diff
 * @property {ImagePayload} hard
 */

/**
 * @typedef {Object} VaeReviewItem
 * @property {string} path Original working dataset image path.
 * @property {string} name
 * @property {number | null} width
 * @property {number | null} height
 * @property {number | null} hf_loss
 * @property {number | null} threshold
 * @property {number | null} diff_threshold
 * @property {boolean} flagged
 * @property {"keep" | "drop"} initial_decision Decision for the original input image.
 * @property {VaeReviewViews} views Review-only Original/VAE/Diff/Hard Mask images.
 */

/**
 * @typedef {Object} UpscaleReviewItem
 * @property {string} path Original working dataset image path.
 * @property {string} name
 * @property {string} uri
 * @property {string} [thumb_uri] Downscaled grid variant.
 * @property {string} [view_uri] Viewport-sized detail variant.
 * @property {number | null} width
 * @property {number | null} height
 * @property {number | null} min_side
 * @property {number | null} threshold The configured upscale_highlight_threshold.
 * @property {boolean} is_jpeg
 * @property {"upscale" | "jpeg_cleanup" | "pass_through"} planned_action
 * @property {boolean} flagged
 * @property {"upscale" | "skip"} initial_decision
 */

/**
 * @typedef {Object} CurateCoveragePoint
 * @property {string} path
 * @property {string} name
 * @property {string} uri
 * @property {string} [thumb_uri] Downscaled hover-tooltip variant.
 * @property {string} [view_uri] Viewport-sized variant.
 * @property {number} x_pct Dot center as a percentage of the coverage image width (0-100).
 * @property {number} y_pct Dot center as a percentage of the coverage image height (0-100).
 */

/**
 * @typedef {Object} CurateDetailsPayload
 * @property {string} report_path
 * @property {ImagePayload | null} coverage_image
 * @property {string | null} coverage_method
 * @property {Record<string, unknown> & {points?: CurateCoveragePoint[]}} coverage
 * @property {{kept_images: number, duplicate_pairs: number, dropped_duplicates: number}} summary
 */

/**
 * @typedef {ImagePayload & {width: number | null, height: number | null}} BucketPoolImage
 *
 * @typedef {Object} BucketPool
 * @property {number} width
 * @property {number} height
 * @property {number} count
 * @property {"empty" | "thin" | "healthy"} status
 * @property {string} suggestion
 * @property {BucketPoolImage[]} images
 *
 * @typedef {Object} BucketPoolDetailsPayload
 * @property {string} report_path
 * @property {number} thin_threshold
 * @property {{total_images: number, populated_buckets: number, thin_buckets: number}} summary
 * @property {BucketPool[]} buckets Configured buckets in project order.
 */

/**
 * @typedef {Object} ExportReviewEntry
 * @property {string} rel Target-relative image path (posix), e.g. "subject/image_01.png".
 * @property {string} path Absolute source image path in the working dataset.
 * @property {string} name
 * @property {string} [uri]
 * @property {string} [thumb_uri]
 * @property {string} [view_uri]
 * @property {"added" | "modified" | "unchanged"} image_status
 * @property {"added" | "modified" | "unchanged"} caption_status
 * @property {boolean} has_caption Whether a .txt sidecar is copied alongside the image.
 */

/**
 * @typedef {Object} ExportReviewPayload
 * @property {string} target_dir
 * @property {ExportReviewEntry[]} added
 * @property {ExportReviewEntry[]} modified
 * @property {string[]} orphaned Target-relative image paths not in the final set (left untouched).
 * @property {{added: number, modified: number, unchanged: number, orphaned: number}} counts
 */

/**
 * @typedef {Object} StepConfigField
 * @property {string} name
 * @property {string} label
 * @property {"select" | "number" | "text" | "checkbox"} control
 * @property {"str" | "int" | "float" | "bool"} value_type
 * @property {{value: string, label: string}[]} options - some fields (e.g. the
 *   UpscaleStep SeedVR2 model) recompute these per request from machine state,
 *   so labels may differ between two payloads for the same step.
 * @property {boolean} allow_custom
 * @property {boolean} nullable
 *
 * @typedef {Object} StepConfigPayload
 * @property {string} step_type
 * @property {StepConfigField[]} fields
 * @property {Object} values
 * @property {string | null} error
 *
 * @typedef {ImagePayload & {seed: number, caption: string, elapsed_ms: number|null, steps: number|null, guidance: number|null, width: number|null, height: number|null, model_id: string|null, truncated: boolean, token_count: number|null}} CaptionPreview
 *
 * `initial_verdict` is seeded by CaptionVerifierStep from the verdict ledger
 * (`reports/caption_verdicts.json`), so re-entering the review opens on what was
 * already decided; it falls back to "correct" when nothing is stored, when the
 * entry was resolved, or when the caption changed underneath it.
 * @typedef {ImagePayload & {width: number|null, height: number|null, caption: string, caption_path: string, has_caption: boolean, initial_verdict: "correct"|"generic"|"wrong"}} CaptionVerifyItem
 *
 * @typedef {Object} CaptionVerifyPayload
 * @property {string} step_type
 * @property {Object} settings
 * @property {("correct"|"generic"|"wrong")[]} verdicts
 * @property {CaptionVerifyItem[]} items
 *
 * One image in the bbox annotation batch. `done` marks an already-captioned
 * image the workspace should leave alone; `verdict` names a caption verdict
 * still in force, which tints the thumbnail. A flagged image always arrives
 * `done: false` so it is re-captioned rather than skipped. Display-only — it is
 * never sent back, since resolution is derived from "a caption was written".
 * @typedef {ImagePayload & {annotations: Object[], done: boolean, verdict: "generic"|"wrong"|null}} BboxAnnotationItem
 *
 * @typedef {Object} BboxAnnotationPayload
 * @property {BboxAnnotationItem[]} images
 *
 * @typedef {Object} PendingInput
 * @property {string} id
 * @property {"source_review" | "bbox_annotation" | "vae_review" | "upscale_review" | "curate_details" | "bucket_pool_details" | "export_review" | "caption_verify" | "step_config"} kind
 * @property {BboxAnnotationPayload | {items: SourceReviewItem[]} | {items: VaeReviewItem[]} | {items: UpscaleReviewItem[]} | CurateDetailsPayload | BucketPoolDetailsPayload | ExportReviewPayload | CaptionVerifyPayload | StepConfigPayload} payload
 */

/**
 * @typedef {Object} JobResult
 * @property {string} output_dir
 * @property {string} reports_dir
 */

/**
 * @typedef {Object} JobPayload
 * @property {string} id
 * @property {JobStatus} status
 * @property {string | null} current_step
 * @property {string | null} current_substep
 * @property {string[]} completed_steps
 * @property {string[]} invalidated_steps Steps whose persisted completion state was cleared for a forced run.
 * @property {string[]} skipped_steps
 * @property {Record<string, string[]>} completed_substeps
 * @property {Record<string, string[]>} skipped_substeps
 * @property {string | null} error
 * @property {JobResult | null} result
 * @property {string[]} logs
 * @property {CaptionStatus | null} caption_status
 * @property {PendingInput | null} pending_input
 * @property {boolean} cancel_requested
 */

/**
 * @typedef {Object} CaptionStatus
 * @property {string} phase CaptionBboxStep: loading/captioning/ready/failed. CaptionVerifierStep adds resolving/loading/generating/idle.
 * @property {string} message
 * @property {string | null} model_id
 * @property {string | null} adapter
 * @property {string | null} device
 * @property {string | null} quantization
 * @property {string | null} dtype
 * @property {number | null} max_pixels
 * @property {string | null} [current_image]
 * @property {string | null} [error]
 * @property {string | null} [family] CaptionVerifierStep only.
 * @property {string | null} [offload] CaptionVerifierStep only.
 * @property {string} [detail] Live sub-progress, e.g. "Loading checkpoint shards · 3/6".
 * @property {number} [progress] 0..1 when the phase can be measured; absent otherwise.
 * @property {number} [elapsed_s] Seconds spent in this phase so far.
 * @property {number} [weights_loaded_bytes] Checkpoint weights loaded so far. Both weight fields are absent until the files are on disk and measurable.
 * @property {number} [weights_total_bytes] Size on disk of the weight files this load reads.
 */

/**
 * @typedef {Object} BoundingBox
 * @property {number} x1 Normalized left edge.
 * @property {number} y1 Normalized top edge.
 * @property {number} x2 Normalized right edge.
 * @property {number} y2 Normalized bottom edge.
 * @property {string} [label]
 * @property {string} [crop_path]
 * @property {string} [crop_name]
 * @property {string} [sidecar_path]
 */

/**
 * @typedef {Object} ProjectCard
 * @property {string} name
 * @property {string | null} input_dir
 * @property {string | null} output_dir
 * @property {string} initials
 * @property {string | null} token
 * @property {"completed" | "running" | "failed" | "draft"} status
 * @property {number} mtime
 * @property {string} [error]
 */

/**
 * @typedef {Object} ProjectMetaPayload
 * @property {string} name
 * @property {string} input_dir
 * @property {string} output_dir
 */

/**
 * One `{value, label}` pair for a Settings dropdown.
 * @typedef {Object} SettingsChoice
 * @property {string} value
 * @property {string} label
 */

/**
 * The stored settings document. Every field is nullable, and `null` always
 * means "not configured — use the app default". There is deliberately no token
 * field: the app reuses whatever the Hugging Face CLI stored.
 *
 * @typedef {Object} AppSettingsDocument
 * @property {number} version
 * @property {{home: string | null}} huggingface
 * @property {{vram_tier: string | null, cuda_device: string | null,
 *             seedvr2_submodule_dir: string | null, seedvr2_model_dir: string | null}} hardware
 * @property {{caption_model_id: string | null, caption_model_task: string | null,
 *             t2i_model_id: string | null, vae_model_id: string | null,
 *             coverage_embedding_model: string | null, seedvr2_dit_model: string | null,
 *             caption_model_type: string | null}} project_defaults
 */

/**
 * Response of `get_settings` / `save_settings`.
 *
 * @typedef {Object} SettingsPayload
 * @property {AppSettingsDocument} settings
 * @property {Record<string, SettingsChoice[]>} choices  dropdown options per field
 * @property {Record<string, string>} placeholders  the app default shown when a field is unset
 * @property {string[]} vram_tiers
 * @property {string} settings_path
 * @property {string} login_command  e.g. "hf auth login"
 * @property {string[]} model_ids  Hub repos worth an access check
 */

/**
 * @typedef {Object} HfStatusPayload
 * @property {{present: boolean, source: "env" | "stored" | null, error: string | null}} token
 * @property {{ok: boolean, name: string | null, error: string | null}} account
 * @property {string} login_command
 */

/**
 * @typedef {Object} ModelAccessResult
 * @property {string} repo_id
 * @property {"ok" | "gated" | "missing" | "unauthorized" | "offline" | "error"} status
 * @property {string} message
 * @property {string} url
 */

/**
 * @typedef {Object} HardwarePayload
 * @property {boolean} cuda
 * @property {number} total_vram_gb
 * @property {"low" | "mid" | "high" | "max" | null} suggested_tier
 */

/**
 * @typedef {Object} PyWebviewApi
 * @property {() => Promise<{project_root: string, default_outputs: string, bootstrap: BootstrapPayload | null}>} app_info
 * @property {() => Promise<{projects: ProjectCard[]}>} list_projects
 * @property {(payload: ProjectMetaPayload) => Promise<{project: ProjectCard}>} create_project
 * @property {(orig_name: string, payload: ProjectMetaPayload) => Promise<{project: ProjectCard}>} update_project
 * @property {(name: string) => Promise<{deleted: boolean}>} delete_project
 * @property {(name: string) => Promise<{project: ProjectCard}>} duplicate_project
 * @property {() => Promise<{path: string | null, error?: string}>} choose_folder
 * @property {(input_dir: string) => Promise<{output_dir: string}>} default_output
 * @property {(project: string, output_dir: string | null) => Promise<ProjectLoadResult>} load_project
 * @property {(input_dir: string, output_dir: string | null) => Promise<ProjectLoadResult>} load_or_create_project_for_input
 * @property {(request: RunRequest) => Promise<{job_id: string}>} start_run
 * @property {(job_id: string) => Promise<{job: JobPayload}>} get_job_status
 * @property {() => Promise<{active: {job_id: string, project: string | null, job: JobPayload} | null}>} active_job
 * @property {(job_id: string, request_id: string, value: unknown) => Promise<{accepted: boolean}>} submit_interaction
 * @property {(job_id: string) => Promise<{cancel_requested: boolean}>} cancel_job
 * @property {() => Promise<{cancel_requested: boolean}>} shutdown
 * @property {(job_id: string, image_path: string, box: BoundingBox) => Promise<{caption: string, crop_path?: string, crop_name?: string, sidecar_path?: string}>} caption_region
 * @property {(job_id: string, image_path: string, caption: string, options?: {reroll?: boolean}) => Promise<CaptionPreview>} generate_caption_preview
 * @property {(kind: string) => Promise<{prompts: {name: string, kind: string, text: string}[]}>} list_caption_prompts
 * @property {(kind: string, name: string, text: string) => Promise<{saved: boolean, prompts: {name: string, kind: string, text: string}[]}>} save_caption_prompt
 * @property {(kind: string, name: string) => Promise<{deleted: boolean, prompts: {name: string, kind: string, text: string}[]}>} delete_caption_prompt
 * @property {(path: string) => Promise<{opened: boolean, error?: string}>} open_path
 * @property {() => Promise<SettingsPayload>} get_settings
 * @property {(payload: object) => Promise<SettingsPayload>} save_settings
 * @property {() => Promise<HfStatusPayload>} hf_status
 * @property {(repo_ids?: string[]) => Promise<{results: ModelAccessResult[]}>} check_model_access
 * @property {() => Promise<HardwarePayload>} detect_hardware
 */

/**
 * @typedef {Window & {pywebview: {api: PyWebviewApi}}} PyWebviewWindow
 */

/**
 * Return the Python bridge injected by pywebview.
 *
 * The bridge methods are implemented by `UiBridge` on the Python side and are
 * asynchronous when called from JavaScript.
 *
 * @returns {PyWebviewApi}
 */
export function api() {
  return /** @type {PyWebviewWindow} */ (globalThis).pywebview.api;
}
