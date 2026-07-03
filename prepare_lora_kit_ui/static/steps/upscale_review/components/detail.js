import { escapeText } from "../../../core/dom.js";
import {
  normalizeUpscaleDecision,
  optionForUpscaleDecision,
  UPSCALE_DECISIONS,
} from "../utils/decisions.js";
import { formatDimensions, formatPlannedAction, formatPx } from "../utils/format.js";

export function renderUpscaleDetail(detail, item, decisions, onChange) {
  if (!item) {
    detail.innerHTML = `
      <div class="upscale-review-empty">
        <strong>No images to review</strong>
        <span>Nothing was flagged for review.</span>
      </div>
    `;
    return;
  }

  const decision = normalizeUpscaleDecision(decisions[item.path]);
  const option = optionForUpscaleDecision(decision);

  detail.innerHTML = `
    <div class="upscale-detail-preview">
      ${item.uri
        ? `<img src="${escapeText(item.view_uri || item.uri)}" alt="${escapeText(item.name)}" />`
        : `<div class="upscale-detail-missing">No preview available</div>`}
    </div>
    <div class="upscale-detail-body">
      <div class="upscale-detail-header">
        <div>
          <strong title="${escapeText(item.name)}">${escapeText(item.name)}</strong>
          <small title="${escapeText(item.path)}">${escapeText(item.path)}</small>
        </div>
        <span class="upscale-decision-pill ${escapeText(decision)}">${escapeText(option.label)}</span>
      </div>
      <div class="upscale-detail-actions" role="group" aria-label="Decision">
        ${UPSCALE_DECISIONS.map(
          (entry) => `
            <button type="button" data-decision="${entry.value}" aria-pressed="${entry.value === decision}">
              ${escapeText(entry.label)}
            </button>
          `,
        ).join("")}
      </div>
      <dl class="upscale-metrics">
        <div><dt>Size</dt><dd>${escapeText(formatDimensions(item))}</dd></div>
        <div><dt>Min side</dt><dd>${escapeText(formatPx(item.min_side))}</dd></div>
        <div><dt>Highlight threshold</dt><dd>${escapeText(formatPx(item.threshold))}</dd></div>
        <div><dt>Planned action</dt><dd>${escapeText(formatPlannedAction(item))}</dd></div>
      </dl>
    </div>
  `;

  detail.querySelectorAll("[data-decision]").forEach((button) => {
    button.addEventListener("click", () => {
      decisions[item.path] = normalizeUpscaleDecision(button.dataset.decision);
      onChange();
    });
  });
}
