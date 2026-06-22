import { api } from "../core/api.js";
import { escapeText } from "../core/dom.js";
import { state } from "../core/state.js";
import { closeModal, showModal } from "./modal.js";

const VAE_DECISIONS = [
  { value: "keep", label: "Keep Input" },
  { value: "drop", label: "Drop Input" },
  { value: "replace", label: "Replace Input" },
];

const VAE_VIEWS = [
  { value: "original", label: "Original" },
  { value: "vae", label: "VAE" },
  { value: "diff", label: "Diff" },
  { value: "hard", label: "Hard Mask" },
];

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
      syncCards(cardsByPath, decisions);
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
      onDecisionChange: renderDetail,
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

  showModal(modal);
}

function vaeReviewModal(itemCount) {
  const modal = document.createElement("div");
  modal.className = "modal vae-review-modal";
  modal.innerHTML = `
    <div class="modal-header">
      <div>
        <h2>VAE Review</h2>
        <p>${itemCount} images · review diagnostics and decide input handling</p>
      </div>
      <button class="primary" id="finishVaeReview">Continue</button>
    </div>
    <div class="vae-review-workspace">
      <div class="vae-review-grid"></div>
      <aside class="vae-review-detail" aria-live="polite"></aside>
    </div>
  `;
  return modal;
}

function vaeReviewCard(item, decisions, { onSelect, onDecisionChange }) {
  const card = document.createElement("div");
  const decision = normalizeVaeDecision(decisions[item.path]);
  card.className = `vae-review-card ${decision}`;
  card.innerHTML = `
    <div class="vae-card-views">
      ${VAE_VIEWS.map((view) => renderVaeThumb(item, view)).join("")}
    </div>
    <div class="vae-card-meta">
      <strong title="${escapeText(item.name)}">${escapeText(item.name)}</strong>
      <small>${escapeText(formatDimensions(item))} · HF ${escapeText(formatNumber(item.hf_loss))}</small>
      <small>${item.flagged ? "flagged outlier" : "within threshold"}</small>
    </div>
    <div class="vae-card-actions" role="group" aria-label="Input decision">
      ${VAE_DECISIONS.map(
        (option) => `
          <button type="button" data-decision="${option.value}">
            ${escapeText(option.label)}
          </button>
        `,
      ).join("")}
    </div>
  `;

  card.addEventListener("click", () => onSelect?.(item));
  card.querySelectorAll("[data-decision]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      decisions[item.path] = normalizeVaeDecision(button.dataset.decision);
      updateVaeCardDecision(card, decisions[item.path]);
      onDecisionChange?.();
    });
  });

  updateVaeCardDecision(card, decision);
  return card;
}

function renderVaeThumb(item, view) {
  const payload = item.views?.[view.value];
  const ratio = aspectRatio(item);
  if (!payload?.uri) {
    return `
      <div class="vae-thumb missing" style="${ratio}">
        <span>${escapeText(view.label)}</span>
      </div>
    `;
  }
  return `
    <figure class="vae-thumb" style="${ratio}">
      <img src="${escapeText(payload.uri)}" alt="${escapeText(`${item.name} ${view.label}`)}" />
      <figcaption>${escapeText(view.label)}</figcaption>
    </figure>
  `;
}

function renderVaeDetail(detail, item, decisions, selectedView, onChange) {
  if (!item) {
    detail.innerHTML = `
      <div class="vae-review-empty">
        <strong>No images to review</strong>
        <span>The VAE gate did not return review items.</span>
      </div>
    `;
    return;
  }

  const view = item.views?.[selectedView.value] ? selectedView.value : "original";
  selectedView.value = view;
  const viewPayload = item.views?.[view];
  const decision = normalizeVaeDecision(decisions[item.path]);
  const option = VAE_DECISIONS.find((entry) => entry.value === decision);

  detail.innerHTML = `
    <div class="vae-detail-preview">
      ${viewPayload?.uri
        ? `<img src="${escapeText(viewPayload.uri)}" alt="${escapeText(`${item.name} ${view}`)}" />`
        : `<div class="vae-detail-missing">No ${escapeText(view)} image available</div>`}
    </div>
    <div class="vae-detail-body">
      <div class="vae-detail-header">
        <div>
          <strong title="${escapeText(item.name)}">${escapeText(item.name)}</strong>
          <small title="${escapeText(item.path)}">${escapeText(item.path)}</small>
        </div>
        <span class="vae-decision-pill ${escapeText(decision)}">${escapeText(option.label)}</span>
      </div>
      <div class="vae-view-tabs" role="group" aria-label="Preview view">
        ${VAE_VIEWS.map(
          (entry) => `
            <button type="button" data-view="${entry.value}" aria-pressed="${entry.value === view}">
              ${escapeText(entry.label)}
            </button>
          `,
        ).join("")}
      </div>
      <div class="vae-detail-actions" role="group" aria-label="Input decision">
        ${VAE_DECISIONS.map(
          (entry) => `
            <button type="button" data-decision="${entry.value}" aria-pressed="${entry.value === decision}">
              ${escapeText(entry.label)}
            </button>
          `,
        ).join("")}
      </div>
      <dl class="vae-metrics">
        <div><dt>Size</dt><dd>${escapeText(formatDimensions(item))}</dd></div>
        <div><dt>HF loss</dt><dd>${escapeText(formatNumber(item.hf_loss))}</dd></div>
        <div><dt>Gate threshold</dt><dd>${escapeText(formatNumber(item.threshold))}</dd></div>
        <div><dt>Diff threshold</dt><dd>${escapeText(formatNumber(item.diff_threshold))}</dd></div>
      </dl>
    </div>
  `;

  detail.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      selectedView.value = button.dataset.view;
      onChange();
    });
  });
  detail.querySelectorAll("[data-decision]").forEach((button) => {
    button.addEventListener("click", () => {
      decisions[item.path] = normalizeVaeDecision(button.dataset.decision);
      onChange();
    });
  });
}

function syncCards(cardsByPath, decisions) {
  cardsByPath.forEach((card, path) => updateVaeCardDecision(card, decisions[path]));
}

function updateVaeCardDecision(card, decision) {
  const normalized = normalizeVaeDecision(decision);
  card.classList.remove(...VAE_DECISIONS.map((entry) => entry.value));
  card.classList.add(normalized);
  card.querySelectorAll("[data-decision]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.decision === normalized));
  });
}

function normalizeVaeDecision(decision) {
  return VAE_DECISIONS.some((entry) => entry.value === decision) ? decision : "keep";
}

function aspectRatio(item) {
  const width = Number(item.width);
  const height = Number(item.height);
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return "";
  }
  return `aspect-ratio: ${width} / ${height}`;
}

function formatDimensions(item) {
  const width = Number(item.width);
  const height = Number(item.height);
  if (!Number.isFinite(width) || !Number.isFinite(height)) return "unknown size";
  return `${width}x${height}`;
}

function formatNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "n/a";
  return number.toFixed(5).replace(/0+$/, "").replace(/\.$/, "");
}
