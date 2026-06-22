import { api } from "../core/api.js";
import { state } from "../core/state.js";
import { closeModal, showModal } from "./modal.js";
import { sourceReviewCard } from "./source_review_card.js";
import { normalizeDecision } from "./source_review_decisions.js";
import { renderSourceReviewDetail } from "./source_review_detail.js";

export function showSourceReview(pending, { onSubmitted }) {
  const items = pending.payload.items || [];
  const decisions = Object.fromEntries(
    items.map((item) => [item.path, normalizeDecision(item.initial_decision)]),
  );

  const modal = sourceReviewModal(items.length);
  const grid = modal.querySelector(".review-grid");
  const detail = modal.querySelector(".source-review-detail");
  const cardsByPath = new Map();

  const renderDetail = (item) => {
    renderSourceReviewDetail(detail, item, item ? decisions[item.path] : null);
  };

  const selectItem = (item) => {
    cardsByPath.forEach((card, path) => {
      card.classList.toggle("selected", path === item.path);
    });
    renderDetail(item);
  };

  const cards = items.map((item) => {
    const card = sourceReviewCard(item, decisions, {
      onSelect: selectItem,
      onDecisionChange: (changedItem) => {
        if (card.classList.contains("selected")) {
          renderDetail(changedItem);
        }
      },
    });
    cardsByPath.set(item.path, card);
    return card;
  });

  grid.replaceChildren(...cards);
  if (items.length > 0) {
    selectItem(items[0]);
  } else {
    renderDetail(null);
  }

  modal.querySelector("#finishReview").addEventListener("click", async () => {
    await api().submit_interaction(state.jobId, pending.id, { decisions });
    closeModal();
    await onSubmitted();
  });

  showModal(modal);
}

function sourceReviewModal(itemCount) {
  const modal = document.createElement("div");
  modal.className = "modal";
  modal.innerHTML = `
    <div class="modal-header">
      <div>
        <h2>Source Review</h2>
        <p>${itemCount} images · choose keep, reject, or flag</p>
      </div>
      <button class="primary" id="finishReview">Continue</button>
    </div>
    <div class="source-review-workspace">
      <div class="review-grid"></div>
      <aside class="source-review-detail" aria-live="polite"></aside>
    </div>
  `;
  return modal;
}
