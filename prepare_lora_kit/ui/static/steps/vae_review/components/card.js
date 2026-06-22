import { escapeText } from "../../../core/dom.js";
import { normalizeVaeDecision, VAE_DECISIONS } from "../utils/decisions.js";
import { VAE_VIEWS } from "../utils/views.js";

export function vaeReviewCard(item, decisions, { onSelect } = {}) {
  const card = document.createElement("div");
  const decision = normalizeVaeDecision(decisions[item.path]);
  card.className = `vae-review-card ${decision}`;
  card.innerHTML = `
    <div class="vae-card-views">
      ${VAE_VIEWS.map((view) => renderVaeThumb(item, view)).join("")}
    </div>
  `;

  card.addEventListener("click", () => onSelect?.(item));

  updateVaeCardDecision(card, decision);
  return card;
}

export function syncVaeCards(cardsByPath, decisions) {
  cardsByPath.forEach((card, path) => {
    updateVaeCardDecision(card, decisions[path]);
  });
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
      <img src="${escapeText(payload.uri)}" alt="${escapeText(`${item.name} ${view.label}`)}" />
      <figcaption>${escapeText(view.label)}</figcaption>
    </figure>
  `;
}

function updateVaeCardDecision(card, decision) {
  const normalized = normalizeVaeDecision(decision);
  card.classList.remove(...VAE_DECISIONS.map((entry) => entry.value));
  card.classList.add(normalized);
}
