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
  const card = reviewCard(item, decisions, {
    className: "vae-review-card",
    title: "Left-click card to show details; right-click card to cycle decision",
    decisionOptions: VAE_DECISIONS,
    normalizeDecision: normalizeVaeDecision,
    renderBody: renderVaeReviewCardBody,
    onSelect,
    onDecisionChange,
  });
  card.classList.toggle("flagged", Boolean(item.flagged));
  return card;
}

export function syncVaeCards(cardsByPath, decisions) {
  syncReviewCards(cardsByPath, decisions, {
    decisionOptions: VAE_DECISIONS,
    normalizeDecision: normalizeVaeDecision,
  });
}

function renderVaeReviewCardBody(item) {
  return `
    ${item.flagged ? '<div class="vae-flag-indicator">Above HF-loss threshold</div>' : ""}
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
      <img loading="lazy" src="${escapeText(payload.thumb_uri || payload.uri)}" alt="${escapeText(`${item.name} ${view.label}`)}" />
      <figcaption>${escapeText(view.label)}</figcaption>
    </figure>
  `;
}
