import { api } from "../core/api.js";
import { $ } from "../core/dom.js";
import { state } from "../+state/index.js";
import { render } from "../shell/render.js";

const TERMINAL_JOB_STATUSES = new Set(["completed", "failed", "cancelled"]);

export async function loadProjects() {
  const result = await api().list_projects();
  state.projects = result.projects || [];

  const select = $("projectSelect");
  const placeholder = new Option("Select project", "");
  const options = state.projects.map((project) => new Option(project, project));
  select.replaceChildren(placeholder, ...options);
}

export async function applyBootstrap(bootstrap) {
  if (!bootstrap) return;

  ensureProjectOption(bootstrap.project);
  $("projectSelect").value = bootstrap.project || "";
  $("inputDir").value = bootstrap.input_dir || "";
  $("outputDir").value = bootstrap.output_dir || "";
  $("tokenInput").value = bootstrap.token || "";
  $("forceInput").checked = Boolean(bootstrap.force);
  state.outputDir = bootstrap.output_dir || "";
  state.outputCustomized = Boolean(state.outputDir);
  state.mockRuntime = Boolean(bootstrap.mock_runtime);
  state.mockProjectName = bootstrap.mock_runtime ? bootstrap.project : null;
  state.mockCurateCoverage = bootstrap.mock_curate_coverage || "auto";

  const result = await api().load_project(
    bootstrap.project,
    bootstrap.output_dir || null,
  );
  applyProjectResult(result, { updateInput: true });

  $("inputDir").value = bootstrap.input_dir || result.input_dir || "";
  $("outputDir").value = bootstrap.output_dir || result.output_dir || "";
  $("tokenInput").value = bootstrap.token || "";
  $("forceInput").checked = Boolean(bootstrap.force);
  state.outputDir = $("outputDir").value;
  state.outputCustomized = Boolean(state.outputDir.trim());
  state.selectedSteps = selectedAvailableSteps(new Set(bootstrap.selected_steps || []));
  state.selectedSubsteps = selectedAvailableSubsteps(state.selectedSteps);
  render();
}

export async function loadProject(options = {}) {
  const name = $("projectSelect").value;
  if (!name) {
    resetProjectSelection();
    return;
  }

  if (options.resetSession === true) {
    state.outputCustomized = false;
  }

  const output = state.outputCustomized
    ? $("outputDir").value.trim() || null
    : null;
  const result = await api().load_project(name, output);
  state.mockRuntime = state.mockProjectName === name;
  applyProjectResult(result, {
    updateInput: true,
    preserveSelection: options.preserveSelection === true,
    resetSession: options.resetSession === true,
  });
}

export async function reloadCurrentProject(options = {}) {
  if ($("inputDir").value.trim() && !$("projectSelect").value) {
    await loadProjectForInput();
    return;
  }

  if ($("projectSelect").value) {
    await loadProject(options);
    return;
  }

  render();
}

export async function loadProjectForInput() {
  const input = $("inputDir").value.trim();
  if (!input) return;

  const output = state.outputCustomized
    ? $("outputDir").value.trim() || null
    : null;
  const result = await api().load_or_create_project_for_input(input, output);

  ensureProjectOption(result.project_name);
  $("projectSelect").value = result.project_name;
  state.mockRuntime = state.mockProjectName === result.project_name;
  applyProjectResult(result, { updateInput: true });
}

export function selectPending() {
  if (!state.project) return;

  state.selectedSteps = defaultActiveSteps();
  state.selectedSubsteps = selectedAvailableSubsteps(state.selectedSteps);
  render();
}

function ensureProjectOption(name) {
  if (!name || state.projects.includes(name)) return;

  state.projects.push(name);
  state.projects.sort();
  $("projectSelect").append(new Option(name, name));
}

function resetProjectSelection() {
  state.project = null;
  state.selectedSteps = new Set();
  state.selectedSubsteps = new Map();
  state.outputDir = "";
  state.outputCustomized = false;
  state.mockRuntime = false;
  state.mockProjectName = null;
  state.mockCurateCoverage = "auto";
  clearTerminalJobState();

  $("inputDir").value = "";
  $("outputDir").value = "";
  $("tokenInput").value = "";
  $("forceInput").checked = false;
  render();
}

function applyProjectResult(result, options = {}) {
  const previousSelectedSteps = options.preserveSelection
    ? new Set(state.selectedSteps)
    : null;

  state.project = result.project;

  if (options.updateInput) {
    $("inputDir").value = result.input_dir || result.project?.input_dir || "";
  }

  if (!state.outputCustomized) {
    state.outputDir = result.output_dir || "";
    $("outputDir").value = state.outputDir;
  }

  state.selectedSteps = previousSelectedSteps
    ? selectedAvailableSteps(previousSelectedSteps)
    : defaultSelectedSteps();
  state.selectedSubsteps = selectedAvailableSubsteps(state.selectedSteps);

  if (options.resetSession) {
    $("tokenInput").value = "";
    $("forceInput").checked = false;
    clearTerminalJobState();
  }

  render();
}

function clearTerminalJobState() {
  if (!TERMINAL_JOB_STATUSES.has(state.job?.status)) return;

  state.jobId = null;
  state.job = null;
  state.runStarting = false;
  state.handledRequestId = null;
}

function defaultSelectedSteps() {
  return defaultActiveSteps();
}

function defaultActiveSteps() {
  return new Set(
    state.project.steps
      .filter((step) => !step.optional)
      .map((step) => step.type),
  );
}

function selectedAvailableSteps(selectedSteps) {
  const available = new Set(state.project.steps.map((step) => step.type));
  return new Set(
    [...selectedSteps].filter((stepType) => available.has(stepType)),
  );
}

function selectedAvailableSubsteps(selectedSteps) {
  const selectedSubsteps = new Map();
  for (const step of state.project.steps) {
    if (!selectedSteps.has(step.type)) continue;
    const values = (step.substeps || [])
      .filter((substep) => substep.enabled !== false)
      .map((substep) => substep.id);
    selectedSubsteps.set(step.type, new Set(values));
  }
  return selectedSubsteps;
}
