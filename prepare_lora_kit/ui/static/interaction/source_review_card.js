import { escapeText } from "../core/dom.js";
import { REVIEW_DECISIONS, normalizeDecision } from "./source_review_decisions.js";
import { formatQuality } from "./source_review_format.js";

export function sourceReviewCard(
  item,
  decisions,
  { onSelect, onDecisionChange } = {},
) {
  const card = document.createElement("div");
  card.className = "review-card";
  card.title = "Left-click card to cycle decision; right-click card to show details";
  card.innerHTML = `
    <img
      src="${escapeText(item.uri)}"
      alt="${escapeText(item.name)}"
      title="Left-click to cycle decision; right-click to show details"
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

  const control = card.querySelector(".review-actions");

  const setDecision = (decision, { notify = true } = {}) => {
    const normalized = normalizeDecision(decision);

    decisions[item.path] = normalized;
    card.classList.remove(...REVIEW_DECISIONS.map((entry) => entry.value));
    card.classList.add(normalized);
    control.querySelectorAll("button").forEach((button) => {
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.decision === normalized),
      );
    });
    if (notify) {
      onDecisionChange?.(item);
    }
  };

  const cycleDecision = (step) => {
    const index = REVIEW_DECISIONS.findIndex(
      (option) => option.value === decisions[item.path],
    );
    const nextIndex =
      (index + step + REVIEW_DECISIONS.length) % REVIEW_DECISIONS.length;
    setDecision(REVIEW_DECISIONS[nextIndex].value);
  };

  control.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      setDecision(button.dataset.decision);
    });
  });

  card.addEventListener("contextmenu", (event) => {
    if (
      event.target instanceof Element &&
      event.target.closest(".review-actions")
    ) {
      return;
    }
    event.preventDefault();
    onSelect?.(item);
  });
  card.addEventListener("click", (event) => {
    event.preventDefault();
    cycleDecision(1);
  });

  setDecision(decisions[item.path], { notify: false });
  return card;
}
