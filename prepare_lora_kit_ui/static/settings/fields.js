/**
 * Field-level markup helpers for the Settings modal.
 *
 * Every field renders the *app default* as placeholder text, so an empty box reads as
 * "not configured, using X" rather than as a missing value.
 */
import { escapeText } from "../core/dom.js";

/** Sentinel option value meaning "the value is in the free-text box below". */
const CUSTOM = "__custom__";

/** A select whose blank option means "not configured". */
export function selectField(name, label, options, placeholder, help = "") {
  const items = (options || [])
    .map((opt) => `<option value="${escapeText(opt.value)}">${escapeText(opt.label)}</option>`)
    .join("");
  return `
    <label class="nf-field settings-field">
      <span class="nf-label">${escapeText(label)}</span>
      <select id="set_${name}" data-setting="${name}" class="nf-select">
        <option value="">${escapeText(unsetLabel(placeholder))}</option>
        ${items}
      </select>
      ${helpMarkup(help)}
    </label>
  `;
}

/**
 * A model picker: a real dropdown over the catalog plus a "Custom…" entry that
 * reveals a free-text box. Custom entries are the point for model fields — the
 * catalogs are a convenience, not an allow-list.
 *
 * Deliberately not a `<datalist>`-backed input: that looks like a dropdown but
 * is a typeahead, filtered against whatever the box already holds, so a field
 * carrying a saved repo id opens onto that one entry and reads as empty. Same
 * control as the project step config (`steps/step_config/step_config.js`).
 */
export function modelField(name, label, options, placeholder, help = "") {
  // No catalog to browse (the VAE has none) — a dropdown holding only "Custom…"
  // is worse than the plain box it would replace.
  if (!(options || []).length) return textField(name, label, placeholder, { help });

  const items = options
    .map(
      (opt) =>
        `<option value="${escapeText(opt.value)}" title="${escapeText(opt.value)}">` +
        `${escapeText(opt.label)}</option>`,
    )
    .join("");
  return `
    <div class="nf-field settings-field">
      <span class="nf-label">${escapeText(label)}</span>
      <select id="set_${name}" data-setting="${name}" class="nf-select">
        <option value="">${escapeText(unsetLabel(placeholder))}</option>
        ${items}
        <option value="${CUSTOM}">Custom…</option>
      </select>
      <input data-setting-custom="${name}" class="nf-input hidden" type="text"
             placeholder="Model id or local path" aria-label="${escapeText(label)} (custom)" />
      ${helpMarkup(help)}
    </div>
  `;
}

/** Show each model field's custom box exactly when "Custom…" is selected. */
export function wireModelFields(modal) {
  for (const select of modal.querySelectorAll("select[data-setting]")) {
    const custom = modal.querySelector(`[data-setting-custom="${select.dataset.setting}"]`);
    if (!custom) continue;
    const sync = () => custom.classList.toggle("hidden", select.value !== CUSTOM);
    select.addEventListener("change", sync);
    sync();
  }
}

/** Put a stored value into one field, routing an off-catalog one to its custom box. */
export function writeField(modal, name, value) {
  const el = modal.querySelector(`[data-setting="${name}"]`);
  if (!el) return;
  const text = value == null ? "" : String(value);
  const custom = modal.querySelector(`[data-setting-custom="${name}"]`);
  if (!custom) {
    el.value = text;
    return;
  }
  // The sentinel is never a real model id, so a value equal to it belongs in
  // the custom box like any other value the catalog does not list.
  const known = text !== CUSTOM && [...el.options].some((option) => option.value === text);
  el.value = known ? text : CUSTOM;
  custom.value = known ? "" : text;
  custom.classList.toggle("hidden", el.value !== CUSTOM);
}

/** Read one field back, preferring the custom box when it is the one in use. */
export function readField(modal, name) {
  const el = modal.querySelector(`[data-setting="${name}"]`);
  if (!el) return "";
  if (el.value !== CUSTOM) return el.value.trim();
  const custom = modal.querySelector(`[data-setting-custom="${name}"]`);
  return custom ? custom.value.trim() : "";
}

/** A free-text field, optionally with a folder Browse button. */
export function textField(name, label, placeholder, { browse = false, help = "" } = {}) {
  const button = browse
    ? `<button type="button" data-browse="${name}" class="nf-btn nf-btn--secondary">Browse</button>`
    : "";
  return `
    <div class="nf-field settings-field">
      <span class="nf-label">${escapeText(label)}</span>
      <div class="nf-inputgroup">
        <input id="set_${name}" data-setting="${name}" class="nf-input" type="text"
               placeholder="${escapeText(placeholder)}" />
        ${button}
      </div>
      ${helpMarkup(help)}
    </div>
  `;
}

function unsetLabel(placeholder) {
  return placeholder ? `Not set — ${placeholder}` : "Not set";
}

function helpMarkup(help) {
  return help ? `<span class="settings-help">${escapeText(help)}</span>` : "";
}
