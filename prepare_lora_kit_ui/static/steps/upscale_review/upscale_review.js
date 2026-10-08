import { api } from "../../core/api.js";
import { state } from "../../+state/index.js";
import { closeModal, modalCancelButton, showModal } from "../../components/modal.js";
import { syncUpscaleCards, upscaleReviewCard } from "./components/card.js";
import { renderUpscaleDetail } from "./components/detail.js";
import { upscaleReviewModal } from "./components/modal.js";
import { upscaleTierSection } from "./components/tier_section.js";
import {
  keepSizeDecision,
  normalizeUpscaleDecision,
  upscaleAllDecision,
} from "./utils/decisions.js";
import { groupByTier } from "./utils/tiers.js";

export function showUpscaleReview(pending, { onSubmitted }) {
  const items = pending.payload.items || [];
  const decisions = Object.fromEntries(
    items.map((item) => [item.path, normalizeUpscaleDecision(item.initial_decision, item)]),
  );
  const tiers = groupByTier(items);

  const modal = upscaleReviewModal(items.length, tiers.length);
  const grid = modal.querySelector(".upscale-review-grid");
  const detail = modal.querySelector(".upscale-review-detail");
  const cardsByPath = new Map();
  let selected = tiers[0]?.items[0] || null;

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

  const buildCard = (item) => {
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
  };

  const applyToTier = (tier, decide) => {
    tier.items.forEach((item) => {
      decisions[item.path] = normalizeUpscaleDecision(decide(item), item);
    });
    syncUpscaleCards(cardsByPath, decisions);
    renderDetail();
  };

  grid.replaceChildren(
    ...tiers.map((tier) =>
      upscaleTierSection(tier, tier.items.map(buildCard), {
        onUpscaleAll: (target) => applyToTier(target, upscaleAllDecision),
        onKeepSize: (target) => applyToTier(target, keepSizeDecision),
      }),
    ),
  );
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
