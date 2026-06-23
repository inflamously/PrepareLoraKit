import { $, escapeText, setText, stepLabel } from "../core/dom.js";
import { state } from "../+state/index.js";

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

export function renderSteps() {
  const list = $("stepList");
  list.replaceChildren();

  if (!state.project) {
    setText("projectSummary", "Select a project and dataset.");
    return;
  }

  const needsDataset = $("inputDir").value.trim() ? "" : " / select dataset";
  const networkType = state.project.network_type
    ? ` / ${state.project.network_type}`
    : "";
  setText(
    "projectSummary",
    `${state.project.name} / ${state.project.network}${networkType}${needsDataset}`,
  );

  for (const step of state.project.steps) {
    list.append(renderStep(step));
  }
}

function renderStep(step) {
  const row = document.createElement("div");
  row.className = "step";

  const disabled = isActiveJob() ? "disabled" : "";
  const running = state.job?.current_step === step.type;
  const status = running ? "running" : step.status;
  const badgeClass = running ? "running" : step.status === "done" ? "done" : "";
  const prereq = step.prerequisites?.length
    ? `Requires ${step.prerequisites.join(", ")}`
    : "No special prerequisites";
  const optional = step.optional ? " · Optional" : "";
  const availableSubsteps = step.substeps || [];
  const checked = state.selectedSteps.has(step.type) ? "checked" : "";

  row.innerHTML = `
    <div class="step-header">
      <input type="checkbox" ${checked} ${disabled} data-step="${escapeText(step.type)}" />
      <button class="step-toggle" type="button" aria-expanded="true" ${disabled}>v</button>
      <div class="step-content">
        <strong>${escapeText(stepLabel(step.type))}</strong>
        <small>${escapeText(step.type)} · ${escapeText(prereq)}${optional}</small>
      </div>
      <span class="badge ${badgeClass}">${escapeText(status)}</span>
    </div>
    <div class="substep-list">
      ${availableSubsteps.map((substep) => renderSubstep(step, substep, disabled)).join("")}
    </div>
  `;

  const parentInput = row.querySelector("input[data-step]");
  parentInput.addEventListener("change", (event) => {
    if (event.target.checked) {
      state.selectedSteps.add(step.type);
      state.selectedSubsteps.set(
        step.type,
        new Set(availableSubsteps
          .filter((substep) => substep.enabled !== false)
          .map((substep) => substep.id)),
      );
    } else {
      state.selectedSteps.delete(step.type);
      state.selectedSubsteps.delete(step.type);
    }
    renderSteps();
  });

  row.querySelector(".step-toggle").addEventListener("click", () => {
    row.classList.toggle("collapsed");
    const expanded = !row.classList.contains("collapsed");
    row.querySelector(".step-toggle").setAttribute("aria-expanded", String(expanded));
  });

  return row;
}

function renderSubstep(step, substep, disabled) {
  const running = state.job?.current_substep === substep.id;
  const status = running
    ? "running"
    : substep.enabled === false
      ? "disabled"
      : substep.status;
  const badgeClass = running ? "running" : substep.status === "done" ? "done" : "";
  const optional = substep.optional ? " · Optional" : "";
  const stateText = substep.enabled === false ? "Disabled" : "Enabled";

  return `
    <div class="substep" aria-disabled="${disabled ? "true" : "false"}">
      <div class="substep-content">
        <strong>${escapeText(substep.label || substep.id)}</strong>
        <small>${escapeText(substep.id)} · ${escapeText(stateText)}${optional}</small>
      </div>
      <span class="badge ${badgeClass}">${escapeText(status)}</span>
    </div>
  `;
}

function isActiveJob() {
  return state.runStarting || (state.job && !TERMINAL_STATUSES.has(state.job.status));
}
