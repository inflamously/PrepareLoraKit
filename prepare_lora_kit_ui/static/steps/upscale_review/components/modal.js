export function upscaleReviewModal(itemCount) {
  const modal = document.createElement("div");
  modal.className = "modal upscale-review-modal";
  modal.innerHTML = `
    <div class="modal-header">
      <div>
        <h2>Upscale Review</h2>
        <p>${itemCount} images flagged · review resolution and JPEG cleanup decisions</p>
      </div>
      <div class="modal-actions">
        <button class="primary" id="finishUpscaleReview">Continue</button>
      </div>
    </div>
    <div class="upscale-review-workspace">
      <div class="upscale-review-grid"></div>
      <aside class="upscale-review-detail" aria-live="polite"></aside>
    </div>
  `;
  return modal;
}
