import { escapeText, stepLabel } from "../../core/dom.js";
import { closeModal, showModal } from "../../components/modal.js";
import { STEP_HELP } from "./help_content.js";

// Open the plain-language help modal for one pipeline step. Wired to the "?"
// button in each step header (see project/view.js). Content comes from the static
// STEP_HELP map — no backend call — so it works even while a job is running.
export function showStepHelp(stepType) {
  const help = STEP_HELP[stepType];
  const title = stepLabel(stepType);

  const modal = document.createElement("div");
  modal.className = "modal modal--compact step-help";

  if (!help) {
    modal.innerHTML = `
      <div class="modal-header">
        <div><h2>${escapeText(title)}</h2></div>
        <button type="button" class="secondary" data-help-close>Close</button>
      </div>
      <div class="step-help__body">
        <p class="step-help__empty">No help is available for this step yet.</p>
      </div>
    `;
    showModal(modal);
    wireClose(modal);
    return;
  }

  const substeps = help.substeps || [];
  const params = help.params || [];

  // Build the sections that actually have content. Each becomes a tab panel when
  // tabs are shown, or a stacked section otherwise.
  const panels = [
    { key: "overview", label: "Overview", html: overviewPanel(help) },
  ];
  if (substeps.length) {
    panels.push({ key: "substeps", label: "Substeps", html: defListPanel(substeps, true) });
  }
  if (params.length) {
    panels.push({ key: "params", label: "Parameters", html: defListPanel(params, false) });
  }

  // Only bother with the tab strip once there's enough content to be worth
  // splitting up; a single short section reads better stacked.
  const useTabs = panels.length >= 3;

  const tabsHtml = useTabs
    ? `<div class="step-help__tabs" role="tablist">
        ${panels.map((p, i) => `
          <button type="button" class="step-help__tab ${i === 0 ? "step-help__tab--active" : ""}"
                  data-tab="${p.key}">${escapeText(p.label)}</button>`).join("")}
      </div>`
    : "";

  const bodyHtml = panels.map((p, i) => {
    if (useTabs) {
      return `<div class="step-help__panel ${i === 0 ? "" : "hidden"}" data-panel="${p.key}">${p.html}</div>`;
    }
    // Stacked: show a small heading per section (except the lead overview).
    const heading = p.key === "overview" ? "" : `<h3 class="step-help__heading">${escapeText(p.label)}</h3>`;
    return `<div class="step-help__panel" data-panel="${p.key}">${heading}${p.html}</div>`;
  }).join("");

  modal.innerHTML = `
    <div class="modal-header">
      <div>
        <h2>${escapeText(title)}</h2>
        <p>${escapeText(help.summary || "")}</p>
      </div>
      <button type="button" class="secondary" data-help-close>Close</button>
    </div>
    ${tabsHtml}
    <div class="step-help__body">${bodyHtml}</div>
  `;

  showModal(modal);
  if (useTabs) wireTabs(modal);
  wireClose(modal);
}

function overviewPanel(help) {
  return `<p class="step-help__detail">${escapeText(help.detail || help.summary || "")}</p>`;
}

// Render substeps / params as a definition-style list of label + description.
// Substeps show their machine id as a muted hint; params do not have one.
function defListPanel(items, withId) {
  return `<dl class="step-help__list">
    ${items.map((item) => `
      <div class="step-help__row">
        <dt class="step-help__term">${escapeText(item.label)}${
          withId && item.id ? ` <span class="step-help__id">${escapeText(item.id)}</span>` : ""
        }</dt>
        <dd class="step-help__desc">${escapeText(item.desc || "")}</dd>
      </div>`).join("")}
  </dl>`;
}

function wireTabs(modal) {
  const tabs = [...modal.querySelectorAll(".step-help__tab")];
  const panels = [...modal.querySelectorAll(".step-help__panel")];
  for (const tab of tabs) {
    tab.addEventListener("click", () => {
      const key = tab.dataset.tab;
      for (const t of tabs) t.classList.toggle("step-help__tab--active", t === tab);
      for (const p of panels) p.classList.toggle("hidden", p.dataset.panel !== key);
    });
  }
}

function wireClose(modal) {
  modal.querySelector("[data-help-close]").addEventListener("click", closeModal);
  // Clicking the dimmed backdrop (the modal layer itself, not the dialog) closes.
  // The listener removes itself so it never lingers on the shared layer element.
  const layer = modal.parentElement;
  if (!layer) return;
  const onBackdrop = (event) => {
    if (event.target !== layer) return;
    layer.removeEventListener("click", onBackdrop);
    closeModal();
  };
  layer.addEventListener("click", onBackdrop);
}
