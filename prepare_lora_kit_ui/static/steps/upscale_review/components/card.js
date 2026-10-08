import { escapeText } from "../../../core/dom.js";
import {
  reviewCard,
  syncReviewCards,
} from "../../../components/review_card.js";
import {
  decisionsFor,
  normalizeUpscaleDecision,
  UPSCALE_DECISIONS,
} from "../utils/decisions.js";

export function upscaleReviewCard(
  item,
  decisions,
  { onSelect, onDecisionChange } = {},
) {
  return reviewCard(item, decisions, {
    className: "upscale-review-card",
    title: "Left-click card to show details; right-click card to cycle decision",
    decisionOptions: decisionsFor(item),
    normalizeDecision: (decision) => normalizeUpscaleDecision(decision, item),
    renderBody: renderUpscaleReviewCardBody,
    onSelect,
    onDecisionChange,
  });
}

export function syncUpscaleCards(cardsByPath, decisions) {
  // Decisions are already normalized per item when set; the full option list
  // just lets the sync clear any previous decision class.
  syncReviewCards(cardsByPath, decisions, {
    decisionOptions: UPSCALE_DECISIONS,
    normalizeDecision: (decision) => normalizeUpscaleDecision(decision),
  });
}

function renderUpscaleReviewCardBody(item) {
  if (!item.uri) {
    return `
      <div class="upscale-thumb missing">
        <span>No preview</span>
      </div>
    `;
  }
  return `
    <figure class="upscale-thumb">
      <img loading="lazy" src="${escapeText(item.thumb_uri || item.uri)}" alt="${escapeText(item.name)}" />
      <figcaption>${escapeText(item.name)}${item.is_jpeg ? " · JPEG" : ""}</figcaption>
    </figure>
  `;
}
