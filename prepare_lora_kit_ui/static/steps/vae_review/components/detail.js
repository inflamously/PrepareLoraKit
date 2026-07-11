import { escapeText } from "../../../core/dom.js";
import {
  normalizeVaeDecision,
  optionForVaeDecision,
  VAE_DECISIONS,
} from "../utils/decisions.js";
import { formatDimensions, formatNumber } from "../utils/format.js";
import { normalizeVaeView, VAE_VIEWS } from "../utils/views.js";

export function renderVaeDetail(detail, item, decisions, selectedView, onChange) {
  if (!item) {
    detail.innerHTML = `
      <div class="vae-review-empty">
        <strong>No images to review</strong>
        <span>The VAE gate did not return review items.</span>
      </div>
    `;
    return;
  }

  const view = normalizeVaeView(item, selectedView.value);
  selectedView.value = view;
  const viewPayload = item.views?.[view];
  const decision = normalizeVaeDecision(decisions[item.path]);
  const option = optionForVaeDecision(decision);

  detail.innerHTML = `
    <div class="vae-detail-preview">
      ${viewPayload?.uri
        ? `<img src="${escapeText(viewPayload.view_uri || viewPayload.uri)}" alt="${escapeText(`${item.name} ${view}`)}" />`
        : `<div class="vae-detail-missing">No ${escapeText(view)} image available</div>`}
    </div>
    <div class="vae-detail-body">
      <div class="vae-detail-header">
        <div>
          <strong title="${escapeText(item.name)}">${escapeText(item.name)}</strong>
          <small title="${escapeText(item.path)}">${escapeText(item.path)}</small>
          ${item.flagged ? '<span class="vae-flag-indicator vae-flag-indicator--detail">Above HF-loss threshold</span>' : ""}
        </div>
        <span class="vae-decision-pill ${escapeText(decision)}">${escapeText(option.label)}</span>
      </div>
      <div class="vae-view-tabs" role="group" aria-label="Preview view">
        ${VAE_VIEWS.map(
          (entry) => `
            <button type="button" data-view="${entry.value}" aria-pressed="${entry.value === view}">
              ${escapeText(entry.label)}
            </button>
          `,
        ).join("")}
      </div>
      <div class="vae-detail-actions" role="group" aria-label="Input decision">
        ${VAE_DECISIONS.map(
          (entry) => `
            <button type="button" data-decision="${entry.value}" aria-pressed="${entry.value === decision}">
              ${escapeText(entry.label)}
            </button>
          `,
        ).join("")}
      </div>
      <dl class="vae-metrics">
        <div><dt>Size</dt><dd>${escapeText(formatDimensions(item))}</dd></div>
        <div><dt>HF loss</dt><dd>${escapeText(formatNumber(item.hf_loss))}</dd></div>
        <div><dt>Gate threshold</dt><dd>${escapeText(formatNumber(item.threshold))}</dd></div>
        <div><dt>Diff threshold</dt><dd>${escapeText(formatNumber(item.diff_threshold))}</dd></div>
        <div><dt>Gate result</dt><dd>${item.flagged ? "Above threshold" : "Within dataset range"}</dd></div>
      </dl>
    </div>
  `;

  detail.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      selectedView.value = button.dataset.view;
      onChange();
    });
  });
  detail.querySelectorAll("[data-decision]").forEach((button) => {
    button.addEventListener("click", () => {
      decisions[item.path] = normalizeVaeDecision(button.dataset.decision);
      onChange();
    });
  });
}
