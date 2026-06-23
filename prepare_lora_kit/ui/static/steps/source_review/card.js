import { escapeText } from "../../core/dom.js";
import { reviewCard } from "../../components/review_card.js";
import { REVIEW_DECISIONS, normalizeDecision } from "./decisions.js";
import { formatQuality } from "./format.js";

export function sourceReviewCard(
  item,
  decisions,
  { onSelect, onDecisionChange } = {},
) {
  return reviewCard(item, decisions, {
    className: "review-card",
    title: "Left-click card to show details; right-click card to cycle decision",
    decisionOptions: REVIEW_DECISIONS,
    normalizeDecision,
    renderBody: renderSourceReviewCardBody,
    onSelect,
    onDecisionChange,
  });
}

function renderSourceReviewCardBody(item) {
  return `
    <img
      src="${escapeText(item.uri)}"
      alt="${escapeText(item.name)}"
      title="Left-click to show details; right-click to cycle decision"
    />
    <div class="review-actions" role="group" aria-label="Review decision">
      <button type="button" data-decision="keep">Keep</button>
      <button type="button" data-decision="reject">Reject</button>
      <button type="button" data-decision="flag">Flag</button>
    </div>
    <div class="review-meta">
      <strong title="${escapeText(item.name)}">${escapeText(item.name)}</strong>
      <small>quality ${escapeText(formatQuality(item.quality))}</small>
      <small title="${escapeText(JSON.stringify(item.scores || {}))}">
        ${(item.auto_reasons || []).map(escapeText).join(", ") || "passes automatic gates"}
      </small>
    </div>
  `;
}
