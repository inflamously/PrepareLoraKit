import { $, escapeText, setText, stepLabel } from "../core/dom.js";
import { state } from "../core/state.js";

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
  const row = document.createElement("label");
  row.className = "step";

  const checked = state.selectedSteps.has(step.type) ? "checked" : "";
  const disabled = isActiveJob() ? "disabled" : "";
  const running = state.job?.current_step === step.type;
  const status = running ? "running" : step.status;
  const badgeClass = running ? "running" : step.status === "done" ? "done" : "";
  const prereq = step.prerequisites?.length
    ? `Requires ${step.prerequisites.join(", ")}`
    : "No special prerequisites";
  const optional = step.optional ? " · Optional" : "";

  row.innerHTML = `
    <input type="checkbox" ${checked} ${disabled} data-step="${escapeText(step.type)}" />
    <div>
      <strong>${escapeText(stepLabel(step.type))}</strong>
      <small>${escapeText(step.type)} · ${escapeText(prereq)}${optional}</small>
    </div>
    <span class="badge ${badgeClass}">${escapeText(status)}</span>
  `;

  row.querySelector("input").addEventListener("change", (event) => {
    if (event.target.checked) {
      state.selectedSteps.add(step.type);
    } else {
      state.selectedSteps.delete(step.type);
    }
  });

  return row;
}

function isActiveJob() {
  return state.runStarting || (state.job && !TERMINAL_STATUSES.has(state.job.status));
}
