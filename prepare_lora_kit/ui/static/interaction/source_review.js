import { api } from "../core/api.js";
import { escapeText } from "../core/dom.js";
import { state } from "../core/state.js";
import { closeModal, showModal } from "./modal.js";

export function showSourceReview(pending, { onSubmitted }) {
  const items = pending.payload.items || [];
  const decisions = Object.fromEntries(
    items.map((item) => [item.path, item.initial_decision || "keep"]),
  );

  const modal = document.createElement("div");
  modal.className = "modal";
  modal.innerHTML = `
    <div class="modal-header">
      <div>
        <h2>Source Review</h2>
        <p>${items.length} images · choose keep, reject, or flag</p>
      </div>
      <button class="primary" id="finishReview">Continue</button>
    </div>
    <div class="review-grid"></div>
  `;

  const grid = modal.querySelector(".review-grid");
  grid.replaceChildren(
    ...items.map((item) => sourceReviewCard(item, decisions)),
  );

  modal.querySelector("#finishReview").addEventListener("click", async () => {
    await api().submit_interaction(state.jobId, pending.id, { decisions });
    closeModal();
    await onSubmitted();
  });

  showModal(modal);
}

function sourceReviewCard(item, decisions) {
  const card = document.createElement("div");
  card.className = `review-card ${decisions[item.path]}`;
  card.innerHTML = `
    <img src="${escapeText(item.uri)}" />
    <div class="review-meta">
      <strong title="${escapeText(item.name)}">${escapeText(item.name)}</strong>
      <small>quality ${escapeText(item.quality)}</small>
      <small title="${escapeText(JSON.stringify(item.scores || {}))}">
        ${(item.auto_reasons || []).map(escapeText).join(", ") || "passes automatic gates"}
      </small>
    </div>
    <div>
      <button data-decision="keep">Keep</button>
      <button data-decision="reject">Reject</button>
      <button data-decision="flag">Flag</button>
    </div>
  `;

  card.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      decisions[item.path] = button.dataset.decision;
      card.className = `review-card ${decisions[item.path]}`;
    });
  });

  return card;
}
