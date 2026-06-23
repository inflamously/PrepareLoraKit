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
  const selectedSubsteps = state.selectedSubsteps.get(step.type) || new Set();
  const availableSubsteps = step.substeps || [];
  const selectedCount = availableSubsteps
    .filter((substep) => selectedSubsteps.has(substep.id))
    .length;
  const checked = state.selectedSteps.has(step.type) && selectedCount > 0 ? "checked" : "";

  row.innerHTML = `
    <div class="step-header">
      <input type="checkbox" ${checked} ${disabled} data-step="${escapeText(step.type)}" />
      <button class="step-toggle" type="button" aria-expanded="true" ${disabled}>v</button>
      <div>
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
  parentInput.indeterminate = selectedCount > 0 && selectedCount < availableSubsteps.length;
  parentInput.addEventListener("change", (event) => {
    if (event.target.checked) {
      state.selectedSteps.add(step.type);
      state.selectedSubsteps.set(
        step.type,
        new Set(availableSubsteps.map((substep) => substep.id)),
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

  for (const input of row.querySelectorAll("input[data-substep]")) {
    input.addEventListener("change", (event) => {
      const next = new Set(state.selectedSubsteps.get(step.type) || []);
      if (event.target.checked) {
        next.add(event.target.dataset.substep);
      } else {
        next.delete(event.target.dataset.substep);
      }
      if (next.size) {
        state.selectedSteps.add(step.type);
        state.selectedSubsteps.set(step.type, next);
      } else {
        state.selectedSteps.delete(step.type);
        state.selectedSubsteps.delete(step.type);
      }
      renderSteps();
    });
  }

  return row;
}

function renderSubstep(step, substep, disabled) {
  const selected = state.selectedSubsteps.get(step.type)?.has(substep.id)
    ? "checked"
    : "";
  const running = state.job?.current_substep === substep.id;
  const status = running ? "running" : substep.status;
  const badgeClass = running ? "running" : substep.status === "done" ? "done" : "";
  const optional = substep.optional ? " · Optional" : "";
  const prereq = substep.prerequisites?.length
    ? `Requires ${substep.prerequisites.join(", ")}`
    : "Ordered substep";

  return `
    <label class="substep">
      <input
        type="checkbox"
        ${selected}
        ${disabled}
        data-step="${escapeText(step.type)}"
        data-substep="${escapeText(substep.id)}"
      />
      <div>
        <strong>${escapeText(substep.label || substep.id)}</strong>
        <small>${escapeText(substep.id)} · ${escapeText(prereq)}${optional}</small>
      </div>
      <span class="badge ${badgeClass}">${escapeText(status)}</span>
    </label>
  `;
}

function isActiveJob() {
  return state.runStarting || (state.job && !TERMINAL_STATUSES.has(state.job.status));
}
