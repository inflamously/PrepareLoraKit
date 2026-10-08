import { escapeText } from "../../../core/dom.js";
import { formatTier } from "../utils/tiers.js";

export function upscaleTierSection(tier, cards, { onUpscaleAll, onKeepSize } = {}) {
  const section = document.createElement("section");
  section.className = "upscale-tier";
  section.dataset.tier = tier.key;
  const count = tier.items.length;
  section.innerHTML = `
    <header class="upscale-tier-header">
      <button type="button" class="upscale-tier-toggle" aria-expanded="true">
        <strong>${escapeText(formatTier(tier))}</strong>
        <small>${count} image${count === 1 ? "" : "s"}</small>
      </button>
      <div class="upscale-tier-actions" role="group" aria-label="Tier decision">
        <button type="button" data-tier-action="upscale">Upscale all</button>
        <button type="button" data-tier-action="keep"
          title="JPEGs become same-size PNGs; other images stay as-is">Keep size</button>
      </div>
    </header>
    <div class="upscale-tier-grid"></div>
  `;

  const grid = section.querySelector(".upscale-tier-grid");
  grid.replaceChildren(...cards);

  const toggle = section.querySelector(".upscale-tier-toggle");
  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!expanded));
    grid.hidden = expanded;
  });
  section
    .querySelector('[data-tier-action="upscale"]')
    .addEventListener("click", () => onUpscaleAll?.(tier));
  section
    .querySelector('[data-tier-action="keep"]')
    .addEventListener("click", () => onKeepSize?.(tier));
  return section;
}
