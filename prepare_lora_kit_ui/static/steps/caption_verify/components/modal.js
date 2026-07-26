import { escapeText } from "../../../core/dom.js";

export function captionVerifyModal(itemCount, settings = {}) {
  const modal = document.createElement("div");
  modal.className = "modal caption-verify-modal";
  const model = settings.model_id || "auto";
  modal.innerHTML = `
    <div class="modal-header">
      <div>
        <h2>Caption Verifier</h2>
        <p>${itemCount} captions · <span id="captionVerifyProgress">0 reviewed</span> · ${escapeText(model)}</p>
      </div>
      <div class="modal-actions">
        <label class="caption-verify-auto">
          <input type="checkbox" class="nf-check" id="captionVerifyAuto" checked />
          Auto-render on select
        </label>
        <button class="primary" id="finishCaptionVerify">Continue</button>
      </div>
    </div>
    <div class="caption-verify-workspace">
      <div class="caption-verify-grid"></div>
      <aside class="caption-verify-preview" aria-live="polite"></aside>
    </div>
  `;
  return modal;
}
