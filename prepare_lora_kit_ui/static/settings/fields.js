/**
 * Field-level markup helpers for the Settings modal.
 *
 * Every field renders the *app default* as placeholder text, so an empty box reads as
 * "not configured, using X" rather than as a missing value.
 */
import { escapeText } from "../core/dom.js";

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
 * A select that also accepts a repo id it has never heard of. Custom entries are
 * the point for model fields: the catalogs are a convenience, not an allow-list.
 */
export function modelField(name, label, options, placeholder, help = "") {
  const items = (options || [])
    .map((opt) => `<option value="${escapeText(opt.value)}">${escapeText(opt.label)}</option>`)
    .join("");
  return `
    <div class="nf-field settings-field">
      <span class="nf-label">${escapeText(label)}</span>
      <div class="nf-inputgroup">
        <input id="set_${name}" data-setting="${name}" class="nf-input" type="text"
               list="list_${name}" placeholder="${escapeText(placeholder)}" />
      </div>
      <datalist id="list_${name}">${items}</datalist>
      ${helpMarkup(help)}
    </div>
  `;
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
