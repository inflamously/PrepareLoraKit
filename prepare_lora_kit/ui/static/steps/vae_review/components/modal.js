export function vaeReviewModal(itemCount) {
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
