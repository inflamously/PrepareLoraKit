import { escapeText } from "../../../core/dom.js";
import {
  decisionsFor,
  normalizeUpscaleDecision,
  optionForUpscaleDecision,
} from "../utils/decisions.js";
import { formatDecisionAction, formatDimensions, formatPx } from "../utils/format.js";
import { formatTier } from "../utils/tiers.js";

export function renderUpscaleDetail(detail, item, decisions, onChange) {
  if (!item) {
    detail.innerHTML = `
      <div class="upscale-review-empty">
        <strong>No images to review</strong>
        <span>No image needs upscaling or cleanup.</span>
      </div>
    `;
    return;
  }

  const decision = normalizeUpscaleDecision(decisions[item.path], item);
  const tier = { lo: item.tier_lo ?? null, hi: item.tier_hi };
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
        ${decisionsFor(item).map(
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
        <div><dt>Tier</dt><dd>${escapeText(formatTier(tier))}</dd></div>
        <div><dt>Highlight threshold</dt><dd>${escapeText(formatPx(item.threshold))}</dd></div>
        <div><dt>Target</dt><dd>${escapeText(formatPx(item.target))}</dd></div>
        <div><dt>Planned action</dt><dd>${escapeText(formatDecisionAction(item, decision))}</dd></div>
      </dl>
    </div>
  `;

  detail.querySelectorAll("[data-decision]").forEach((button) => {
    button.addEventListener("click", () => {
      decisions[item.path] = normalizeUpscaleDecision(button.dataset.decision, item);
      onChange();
    });
  });
}
