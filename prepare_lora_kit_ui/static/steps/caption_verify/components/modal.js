import { escapeText } from "../../../core/dom.js";

// Three fixed rows: header, workspace (caption editor beside the compare pane)
// and the dataset filmstrip. The gallery used to be the workspace itself, which
// put a caption box, a verdict trio and a thumbnail in every tile *and* the
// selected caption again in the preview — the strip demotes navigation to what
// it is, so exactly one caption is editable and exactly one verdict is on show.
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
        <!-- Off by default: the first render of a run also pays for the model
             load, which is minutes for a 9B model, so merely stepping to the
             next image must not start one. Same reasoning selectAt() already
             applies to the image the modal opens on. -->
        <label class="caption-verify-auto">
          <input type="checkbox" class="nf-check" id="captionVerifyAuto" />
          Auto-render on select
        </label>
        <button class="primary" id="finishCaptionVerify">Continue</button>
      </div>
    </div>
    <div class="caption-verify-workspace">
      <section class="caption-verify-editor"></section>
      <aside class="caption-verify-preview" aria-live="polite"></aside>
    </div>
    <footer class="caption-verify-strip">
      <div class="caption-verify-strip__head">
        <span>Dataset · ${itemCount} image${itemCount === 1 ? "" : "s"}</span>
        <div class="caption-verify-strip__nav">
          <button type="button" class="nf-btn caption-verify-nav" id="captionVerifyPrev"
                  title="Previous image" aria-label="Previous image">&lsaquo;</button>
          <button type="button" class="nf-btn caption-verify-nav" id="captionVerifyNext"
                  title="Next image" aria-label="Next image">&rsaquo;</button>
        </div>
      </div>
      <div class="caption-verify-tiles" id="captionVerifyTiles"></div>
    </footer>
  `;
  return modal;
}
