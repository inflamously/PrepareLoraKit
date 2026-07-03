import { api } from "../../core/api.js";
import { state } from "../../+state/index.js";
import { closeModal, modalCancelButton, showModal } from "../../components/modal.js";
import { syncUpscaleCards, upscaleReviewCard } from "./components/card.js";
import { renderUpscaleDetail } from "./components/detail.js";
import { upscaleReviewModal } from "./components/modal.js";
import { normalizeUpscaleDecision } from "./utils/decisions.js";

export function showUpscaleReview(pending, { onSubmitted }) {
  const items = pending.payload.items || [];
  const decisions = Object.fromEntries(
    items.map((item) => [item.path, normalizeUpscaleDecision(item.initial_decision)]),
  );

  const modal = upscaleReviewModal(items.length);
  const grid = modal.querySelector(".upscale-review-grid");
  const detail = modal.querySelector(".upscale-review-detail");
  const cardsByPath = new Map();
  let selected = items[0] || null;

  const renderDetail = () => {
    renderUpscaleDetail(detail, selected, decisions, () => {
      syncUpscaleCards(cardsByPath, decisions);
      renderDetail();
    });
  };

  const selectItem = (item) => {
    selected = item;
    cardsByPath.forEach((card, path) => {
      card.classList.toggle("selected", path === item.path);
    });
    renderDetail();
  };

  const cards = items.map((item) => {
    const card = upscaleReviewCard(item, decisions, {
      onSelect: selectItem,
      onDecisionChange: (changedItem) => {
        if (card.classList.contains("selected")) {
          selected = changedItem;
          renderDetail();
        }
      },
    });
    cardsByPath.set(item.path, card);
    return card;
  });

  grid.replaceChildren(...cards);
  if (selected) {
    selectItem(selected);
  } else {
    renderDetail();
  }

  modal.querySelector("#finishUpscaleReview").addEventListener("click", async () => {
    await api().submit_interaction(state.jobId, pending.id, { decisions });
    closeModal();
    await onSubmitted();
  });

  const actions = modal.querySelector(".modal-actions");
  actions.insertBefore(modalCancelButton(onSubmitted), actions.firstChild);

  showModal(modal);
}
