import { api } from "../core/api.js";
import { $ } from "../core/dom.js";
import { state } from "../core/state.js";
import {
  applyCaptionConfigDefaults,
  resetCaptionConfigDefaults,
} from "../caption/config.js";
import { render } from "../shell/render.js";

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
  render();
}

export async function loadProject(options = {}) {
  const name = $("projectSelect").value;
  if (!name) {
    resetProjectSelection();
    return;
  }

  const output = state.outputCustomized
    ? $("outputDir").value.trim() || null
    : null;
  const result = await api().load_project(name, output);
  state.mockRuntime = state.mockProjectName === name;
  applyProjectResult(result, {
    updateInput: true,
    preserveSelection: options.preserveSelection === true,
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

  state.selectedSteps = new Set(
    state.project.steps
      .filter((step) => step.status !== "done")
      .map((step) => step.type),
  );
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
  state.outputDir = "";
  state.outputCustomized = false;
  state.mockRuntime = false;
  state.mockProjectName = null;

  $("inputDir").value = "";
  $("outputDir").value = "";
  $("tokenInput").value = "";
  $("forceInput").checked = false;
  resetCaptionConfigDefaults();
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

  applyCaptionConfigDefaults();
  render();
}

function defaultSelectedSteps() {
  const pending = new Set(
    state.project.steps
      .filter((step) => step.status !== "done")
      .map((step) => step.type),
  );

  return pending.size
    ? pending
    : new Set(state.project.steps.map((step) => step.type));
}

function selectedAvailableSteps(selectedSteps) {
  const available = new Set(state.project.steps.map((step) => step.type));
  return new Set(
    [...selectedSteps].filter((stepType) => available.has(stepType)),
  );
}
