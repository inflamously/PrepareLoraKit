import { escapeText } from "../../core/dom.js";

// A region still needs a caption if its label is blank or still the auto-filled
// "region N" placeholder produced by canvas.js when the box was drawn. The regex
// only matches "region" + digits, so real captions like "region of interest" are
// left untouched.
const PLACEHOLDER_RE = /^region\s+\d+$/i;
export function isUncaptioned(box) {
  const label = (box.label || "").trim();
  return label === "" || PLACEHOLDER_RE.test(label);
}

// Build the "Annotate Regions" workspace modal. Stateless markup builder kept out
// of the Annotator class; the class queries it for the elements it wires up and
// the ThumbnailStrip fills #thumbStrip. `count` is the number of images in the batch.
export function annotatorModal(count) {
  const plural = count === 1 ? "" : "s";
  const modal = document.createElement("div");
  modal.className = "modal";
  modal.innerHTML = `
    <div class="modal-header">
      <div>
        <h2>Annotate Regions</h2>
        <p id="annotateImageName">${count} image${plural} · drag on the image to add a box</p>
      </div>
      <div class="modal-actions">
        <button id="clearBoxes" class="secondary">Clear all boxes</button>
        <button id="captionBox" class="primary">Caption selected box</button>
        <button class="primary" id="doneAnnotate">Done</button>
      </div>
    </div>
    <div class="annotator">
      <div class="canvas-wrap"><canvas id="annotationCanvas"></canvas></div>
      <div class="box-panel">
        <label class="hide-boxes"><input class="nf-check" type="checkbox" id="hideBoxesToggle" /> <span>Hide boxes</span></label>
        <div id="bboxStatus" class="bbox-status">No box selected</div>
        <div id="captionModelStatus" class="caption-status hidden"></div>
        <div id="boxList"></div>
      </div>
    </div>
    <div class="modal-footer">
      <div id="thumbStrip" class="thumb-strip"></div>
      <div class="modal-footer__actions">
        <button id="skipAllAnnotate" class="danger">Skip all remaining</button>
        <button id="skipAnnotate" class="secondary">Skip image</button>
      </div>
    </div>
  `;
  return modal;
}
