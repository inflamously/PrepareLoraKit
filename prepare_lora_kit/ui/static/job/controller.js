import { api } from "../core/api.js";
import { $, setText } from "../core/dom.js";
import { state } from "../core/state.js";
import { selectedCaptionModel } from "../caption/config.js";
import { showAnnotator } from "../steps/bbox_annotation/bbox_annotation.js";
import { showCurateDetails } from "../steps/curate_details/curate_details.js";
import { showSourceReview } from "../steps/source_review/source_review.js";
import { showVaeReview } from "../steps/vae_review/vae_review.js";
import { loadProject } from "../project/controller.js";
import { selectedStepArray } from "../project/selection.js";
import { render } from "../shell/render.js";

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

export async function startRun() {
  if (state.runStarting || isActiveJob(state.job)) return;

  try {
    const request = buildRunRequest();
    state.runStarting = true;
    state.job = {
      status: "queued",
      current_step: null,
      logs: [],
      cancel_requested: false,
      result: null,
    };
    render();

    const result = await api().start_run(request);
    state.jobId = result.job_id;
    state.handledRequestId = null;
    pollJob();
  } catch (err) {
    state.runStarting = false;
    if (state.job?.status === "queued" && !state.jobId) {
      state.job = null;
    }
    render();
    alert(err.message || String(err));
  }
}

export async function cancelRun() {
  if (!state.jobId) return;

  $("cancelButton").disabled = true;
  $("cancelButton").textContent = "Cancelling...";
  setText("jobSummary", "Cancellation requested");

  await api().cancel_job(state.jobId);
  await pollJob();
}

export async function openOutput() {
  const outputDir = state.job?.result?.output_dir;
  if (outputDir) {
    await api().open_path(outputDir);
  }
}

export async function pollJob() {
  if (!state.jobId) return;

  const result = await api().get_job_status(state.jobId);
  state.job = result.job;
  state.runStarting = false;
  render();

  handlePendingInput(state.job.pending_input);

  if (TERMINAL_STATUSES.has(state.job.status)) {
    await loadProject({ preserveSelection: true });
    return;
  }

  globalThis.setTimeout(pollJob, 800);
}

function isActiveJob(job) {
  return job && !TERMINAL_STATUSES.has(job.status);
}

function buildRunRequest() {
  const inputDir = $("inputDir").value.trim();
  if (!inputDir) throw new Error("Choose a dataset folder.");
  if (!$("projectSelect").value) throw new Error("Select a project.");

  const steps = selectedStepArray();
  if (!steps.length) throw new Error("Select at least one step.");

  return {
    input_dir: inputDir,
    output_dir: $("outputDir").value.trim() || null,
    project: $("projectSelect").value,
    token: $("tokenInput").value.trim() || null,
    force: $("forceInput").checked,
    caption_model_id: selectedCaptionModel() || null,
    caption_vram_mode: $("captionVramMode").value || "auto",
    mock_runtime: state.mockRuntime === true,
    mock_curate_coverage:
      state.mockRuntime === true ? state.mockCurateCoverage : "auto",
    steps,
  };
}

function handlePendingInput(pending) {
  if (!pending || pending.id === state.handledRequestId) return;

  state.handledRequestId = pending.id;

  if (pending.kind === "source_review") {
    showSourceReview(pending, { onSubmitted: pollJob });
  }

  if (pending.kind === "curate_details") {
    showCurateDetails(pending, { onSubmitted: pollJob });
  }

  if (pending.kind === "bbox_annotation") {
    showAnnotator(pending, { onSubmitted: pollJob });
  }

  if (pending.kind === "vae_review") {
    showVaeReview(pending, { onSubmitted: pollJob });
  }
}
