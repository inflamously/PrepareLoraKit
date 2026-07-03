import { api } from "../../core/api.js";
import { state } from "../../+state/index.js";
import { closeModal, modalCancelButton, showModal } from "../../components/modal.js";
import { vaeReviewCard, syncVaeCards } from "./components/card.js";
import { renderVaeDetail } from "./components/detail.js";
import { vaeReviewModal } from "./components/modal.js";
import { normalizeVaeDecision } from "./utils/decisions.js";

export function showVaeReview(pending, { onSubmitted }) {
  const items = pending.payload.items || [];
  const decisions = Object.fromEntries(
    items.map((item) => [item.path, normalizeVaeDecision(item.initial_decision)]),
  );
  const selectedView = { value: "original" };

  const modal = vaeReviewModal(items.length);
  const grid = modal.querySelector(".vae-review-grid");
  const detail = modal.querySelector(".vae-review-detail");
  const cardsByPath = new Map();
  let selected = items[0] || null;

  const renderDetail = () => {
    renderVaeDetail(detail, selected, decisions, selectedView, () => {
      syncVaeCards(cardsByPath, decisions);
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
    const card = vaeReviewCard(item, decisions, {
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

  modal.querySelector("#finishVaeReview").addEventListener("click", async () => {
    await api().submit_interaction(state.jobId, pending.id, { decisions });
    closeModal();
    await onSubmitted();
  });

  const actions = modal.querySelector(".modal-actions");
  actions.insertBefore(modalCancelButton(onSubmitted), actions.firstChild);

  showModal(modal);
}
