/**
 * @typedef {"queued" | "running" | "waiting_input" | "cancelling" | "completed" | "failed" | "cancelled"} JobStatus
 */

/**
 * @typedef {Object} SubstepPayload
 * @property {string} id
 * @property {string} label
 * @property {boolean} enabled
 * @property {string} status
 * @property {string[]} prerequisites
 * @property {boolean} optional
 */

/**
 * @typedef {Object} StepPayload
 * @property {string} type
 * @property {Record<string, unknown>} config
 * @property {string} status
 * @property {string[]} prerequisites
 * @property {boolean} optional
 * @property {SubstepPayload[]} substeps
 */

/**
 * @typedef {Object} ProjectPayload
 * @property {string} name
 * @property {string} network
 * @property {string} network_type
 * @property {string | null} input_dir
 * @property {StepPayload[]} steps
 */

/**
 * @typedef {Object} ProjectLoadResult
 * @property {ProjectPayload} project
 * @property {string} project_name
 * @property {string | null} input_dir
 * @property {string | null} output_dir
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
 * @property {string} uri
 */

/**
 * @typedef {Object} SourceReviewItem
 * @property {string} path
 * @property {string} name
 * @property {string} uri
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
 * @property {"keep" | "drop" | "replace"} initial_decision Decision for the original input image.
 * @property {VaeReviewViews} views Review-only Original/VAE/Diff/Hard Mask images.
 */

/**
 * @typedef {Object} CurateDetailsPayload
 * @property {string} report_path
 * @property {ImagePayload | null} coverage_image
 * @property {string | null} coverage_method
 * @property {Record<string, unknown>} coverage
 * @property {{kept_images: number, duplicate_pairs: number, dropped_duplicates: number}} summary
 */

/**
 * @typedef {Object} StepConfigField
 * @property {string} name
 * @property {string} label
 * @property {"select" | "number" | "text" | "checkbox"} control
 * @property {"str" | "int" | "float" | "bool"} value_type
 * @property {{value: string, label: string}[]} options
 * @property {boolean} allow_custom
 * @property {boolean} nullable
 *
 * @typedef {Object} StepConfigPayload
 * @property {string} step_type
 * @property {StepConfigField[]} fields
 * @property {Object} values
 * @property {string | null} error
 *
 * @typedef {Object} PendingInput
 * @property {string} id
 * @property {"source_review" | "bbox_annotation" | "vae_review" | "curate_details" | "step_config"} kind
 * @property {ImagePayload | {items: SourceReviewItem[]} | {items: VaeReviewItem[]} | CurateDetailsPayload | StepConfigPayload} payload
 */

/**
 * @typedef {Object} JobResult
 * @property {string} output_dir
 * @property {string} reports_dir
 * @property {string} run_config
 */

/**
 * @typedef {Object} JobPayload
 * @property {string} id
 * @property {JobStatus} status
 * @property {string | null} current_step
 * @property {string | null} current_substep
 * @property {string[]} completed_steps
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
 * @property {string} phase
 * @property {string} message
 * @property {string | null} model_id
 * @property {string | null} adapter
 * @property {string | null} device
 * @property {string | null} quantization
 * @property {string | null} dtype
 * @property {number | null} max_pixels
 * @property {string | null} [current_image]
 * @property {string | null} [error]
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
 * @property {string | null} network
 * @property {string | null} network_type
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
 * @property {string} network
 */

/**
 * @typedef {Object} PyWebviewApi
 * @property {() => Promise<{project_root: string, default_outputs: string, bootstrap: BootstrapPayload | null}>} app_info
 * @property {() => Promise<{projects: ProjectCard[]}>} list_projects
 * @property {() => Promise<{networks: string[]}>} list_networks
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
 * @property {(kind: string) => Promise<{prompts: {name: string, kind: string, text: string}[]}>} list_caption_prompts
 * @property {(kind: string, name: string, text: string) => Promise<{saved: boolean, prompts: {name: string, kind: string, text: string}[]}>} save_caption_prompt
 * @property {(kind: string, name: string) => Promise<{deleted: boolean, prompts: {name: string, kind: string, text: string}[]}>} delete_caption_prompt
 * @property {(path: string) => Promise<{opened: boolean, error?: string}>} open_path
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
