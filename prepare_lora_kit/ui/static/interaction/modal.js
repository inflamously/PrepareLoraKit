import { $ } from "../core/dom.js";

export function showModal(inner) {
  const layer = $("modalLayer");
  layer.replaceChildren(inner);
  layer.classList.remove("hidden");
}

export function closeModal() {
  const layer = $("modalLayer");
  layer.classList.add("hidden");
  layer.replaceChildren();
}
