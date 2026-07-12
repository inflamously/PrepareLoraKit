import { $, escapeText, setText, stepLabel } from "../core/dom.js";
import { state } from "../+state/index.js";
import { showStepHelp } from "../steps/step_help/step_help.js";

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

export function renderSteps() {
  const list = $("stepList");
  // While the run is paused on a modal interaction the step list can't change.
  // Skip the rebuild so the 800ms poll doesn't blur modal inputs (e.g. the
  // caption prompt textarea) by tearing down and recreating the #stepList DOM.
  if (state.job?.status === "waiting_input" && list.childElementCount) return;

  list.replaceChildren();

  if (!state.project) {
    setText("projectSummary", "Select a project and dataset.");
    return;
  }

  const needsDataset = state.inputDir.trim() ? "" : " / select dataset";
  setText(
    "projectSummary",
    `${state.project.name}${needsDataset}`,
  );

  for (const step of state.project.steps) {
    list.append(renderStep(step));
  }
}

function renderStep(step) {
  const row = document.createElement("div");
  const disabled = isActiveJob() ? "disabled" : "";
  const running = state.job?.current_step === step.type;
  const completed = state.job?.completed_steps?.includes(step.type);
  const invalidated = state.job?.invalidated_steps?.includes(step.type);
  const status = completed
    ? "done"
    : running
      ? "running"
      : invalidated
        ? "pending"
        : step.status;
  const prereq = step.prerequisites?.length
    ? `Requires ${step.prerequisites.join(", ")}`
    : "No special prerequisites";
  const optional = step.optional ? " - Optional" : "";
  const availableSubsteps = step.substeps || [];
  const checked = state.selectedSteps.has(step.type) ? "checked" : "";
  const collapsed = state.collapsedSteps.has(step.type);
  const attention = step.needs_attention ? attentionHint(step.attention) : "";
  row.className = [
    "step",
    "nf-step",
    checked ? "is-checked" : "nf-step--disabled",
    running ? "nf-step--active" : "",
    step.needs_attention ? "nf-step--attention" : "",
    collapsed ? "collapsed" : "",
  ].filter(Boolean).join(" ");
  if (attention) {
    row.title = attention;
  }

  row.innerHTML = `
    <div class="nf-step__lead">
      <input class="nf-check" type="checkbox" ${checked} ${disabled} data-step="${escapeText(step.type)}" />
      <button class="step-toggle nf-step__caret" type="button" aria-expanded="${!collapsed}" ${disabled}>${collapsed ? "▸" : "▾"}</button>
    </div>
    <div class="step-content nf-step__body">
      <strong class="nf-step__title">${escapeText(stepLabel(step.type))}</strong>
      <small class="nf-step__meta">${escapeText(step.type)} <span class="nf-sep">&middot;</span> ${escapeText(prereq)}${optional}${
        attention ? ` <span class="nf-step__hint">&middot; recommended</span>` : ""
      }</small>
    </div>
    <span class="step-status nf-step__status ${pillClass(status)}">${escapeText(status)}</span>
    <button class="nf-step__help" type="button" title="What does this step do?" aria-label="Step help">?</button>
    <div class="substep-list">
      ${availableSubsteps.map((substep) => renderSubstep(step, substep, disabled)).join("")}
    </div>
  `;

  if (availableSubsteps.length === 0) {
    row.querySelector(".step-toggle").classList.add("is-empty");
    row.querySelector(".step-toggle").disabled = true;
  }

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

  // Help is always available — intentionally not gated by `disabled` so users
  // can read what a step does even while a job is running.
  row.querySelector(".nf-step__help").addEventListener("click", (event) => {
    event.stopPropagation();
    showStepHelp(step.type);
  });

  row.querySelector(".step-toggle").addEventListener("click", () => {
    if (state.collapsedSteps.has(step.type)) {
      state.collapsedSteps.delete(step.type);
    } else {
      state.collapsedSteps.add(step.type);
    }
    renderSteps();
  });

  return row;
}

function renderSubstep(step, substep, disabled) {
  const running = state.job?.current_substep === substep.id;
  const completed = state.job?.completed_substeps?.[step.type]?.includes(substep.id);
  const invalidated = state.job?.invalidated_steps?.includes(step.type);
  const status = completed
    ? "done"
    : running
      ? "running"
      : substep.enabled === false
        ? "disabled"
        : invalidated
          ? "pending"
          : substep.status;
  const optional = substep.optional ? " - Optional" : "";
  const stateText = substep.enabled === false ? "Disabled" : "Enabled";

  return `
    <div class="substep nf-step" aria-disabled="${disabled ? "true" : "false"}">
      <div class="substep-content nf-step__body">
        <strong class="nf-step__title">${escapeText(substep.label || substep.id)}</strong>
        <small class="nf-step__meta">${escapeText(substep.id)} <span class="nf-sep">&middot;</span> ${escapeText(stateText)}${optional}</small>
      </div>
      <span class="step-status nf-step__status ${pillClass(status)}">${escapeText(status)}</span>
    </div>
  `;
}

function pillClass(status) {
  if (status === "done" || status === "completed") {
    return "nf-pill nf-pill--done";
  }
  if (status === "running") {
    return "nf-pill nf-pill--info";
  }
  if (status === "waiting" || status === "queued" || status === "cancelling") {
    return "nf-pill nf-pill--warning";
  }
  if (status === "failed" || status === "cancelled" || status === "error") {
    return "nf-pill nf-pill--danger";
  }
  return "nf-pill nf-pill--muted";
}

function isActiveJob() {
  return state.runStarting || (state.job && !TERMINAL_STATUSES.has(state.job.status));
}

// Tooltip text explaining why a step is softly highlighted (e.g. UpscaleStep when
// the dataset has undersized images or JPEG artifacts).
function attentionHint(attention) {
  const undersized = Number(attention?.undersized) || 0;
  const jpeg = Number(attention?.jpeg) || 0;
  const parts = [];
  if (undersized) parts.push(`${undersized} image${undersized === 1 ? "" : "s"} ≤ threshold`);
  if (jpeg) parts.push(`${jpeg} JPEG${jpeg === 1 ? "" : "s"}`);
  if (!parts.length) return "Recommended for this dataset";
  return `Recommended — ${parts.join(", ")} (upscale / clean up before training)`;
}
