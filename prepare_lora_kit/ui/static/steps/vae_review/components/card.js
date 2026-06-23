import { escapeText } from "../../../core/dom.js";
import {
  reviewCard,
  syncReviewCards,
} from "../../../components/review_card.js";
import { normalizeVaeDecision, VAE_DECISIONS } from "../utils/decisions.js";
import { VAE_VIEWS } from "../utils/views.js";

export function vaeReviewCard(
  item,
  decisions,
  { onSelect, onDecisionChange } = {},
) {
  return reviewCard(item, decisions, {
    className: "vae-review-card",
    title: "Left-click card to show details; right-click card to cycle decision",
    decisionOptions: VAE_DECISIONS,
    normalizeDecision: normalizeVaeDecision,
    renderBody: renderVaeReviewCardBody,
    onSelect,
    onDecisionChange,
  });
}

export function syncVaeCards(cardsByPath, decisions) {
  syncReviewCards(cardsByPath, decisions, {
    decisionOptions: VAE_DECISIONS,
    normalizeDecision: normalizeVaeDecision,
  });
}

function renderVaeReviewCardBody(item) {
  return `
    <div class="vae-card-views">
      ${VAE_VIEWS.map((view) => renderVaeThumb(item, view)).join("")}
    </div>
  `;
}

function renderVaeThumb(item, view) {
  const payload = item.views?.[view.value];
  if (!payload?.uri) {
    return `
      <div class="vae-thumb missing">
        <span>${escapeText(view.label)}</span>
      </div>
    `;
  }
  return `
    <figure class="vae-thumb">
      <img src="${escapeText(payload.uri)}" alt="${escapeText(`${item.name} ${view.label}`)}" />
      <figcaption>${escapeText(view.label)}</figcaption>
    </figure>
  `;
}
