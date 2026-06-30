import { escapeText } from "../../core/dom.js";
import { imageStripState } from "./batch.js";

// Footer strip of image thumbnails for the annotation workspace. Clicking a
// thumbnail switches the active image; per-thumbnail badges show done / has-boxes
// / skipped state so the user can see what is left at a glance. Uses lazy <img>
// (not canvas) so the browser decodes/caches off-screen thumbs cheaply.
export class ThumbnailStrip {
  constructor({ container, states, getBusy, onSelect }) {
    this.container = container;
    this.states = states;
    this.getBusy = getBusy;
    this.onSelect = onSelect;
    this.activeIndex = 0;
    this.onClick = this.onClick.bind(this);
  }

  render() {
    this.container.replaceChildren();
    this.states.forEach((state, index) => {
      const thumb = document.createElement("button");
      thumb.type = "button";
      thumb.className = "thumb";
      thumb.dataset.index = String(index);
      thumb.title = state.name || "";
      thumb.innerHTML = `
        <img class="thumb__img" loading="lazy" alt="${escapeText(state.name || "")}"
             src="${escapeText(state.uri || "")}" />
        <span class="thumb__badge"></span>
      `;
      this.container.appendChild(thumb);
      this.refreshState(index);
    });
    this.container.addEventListener("click", this.onClick);
    this.setActive(this.activeIndex);
  }

  thumbAt(index) {
    return this.container.querySelector(`.thumb[data-index="${index}"]`);
  }

  // Recompute one thumbnail's badge after its image's boxes changed.
  refreshState(index) {
    const thumb = this.thumbAt(index);
    if (!thumb) return;
    thumb.classList.remove(
      "thumb--done",
      "thumb--has-boxes",
      "thumb--skipped",
      "thumb--empty",
    );
    thumb.classList.add(`thumb--${imageStripState(this.states[index])}`);
  }

  setActive(index) {
    this.activeIndex = index;
    this.container.querySelectorAll(".thumb").forEach((el) => {
      el.classList.toggle("thumb--current", Number(el.dataset.index) === index);
    });
    this.thumbAt(index)?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }

  setBusy(busy) {
    this.container.querySelectorAll(".thumb").forEach((el) => {
      el.disabled = busy;
    });
  }

  onClick(event) {
    if (this.getBusy?.()) return;
    const thumb = event.target.closest?.(".thumb");
    if (!thumb || !this.container.contains(thumb)) return;
    const index = Number(thumb.dataset.index);
    if (!Number.isNaN(index)) this.onSelect(index);
  }

  cleanup() {
    this.container.removeEventListener("click", this.onClick);
  }
}
