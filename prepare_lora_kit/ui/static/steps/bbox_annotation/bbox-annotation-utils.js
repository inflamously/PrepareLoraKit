import { escapeText } from "../../core/dom.js";

// Build the "Annotate Regions" modal element. Stateless markup builder kept out
// of the Annotator class; the class queries it for the elements it wires up.
export function annotatorModal(image) {
  const modal = document.createElement("div");
  modal.className = "modal";
  modal.innerHTML = `
    <div class="modal-header">
      <div>
        <h2>Annotate Regions</h2>
        <p>${escapeText(image.name)} · drag on the image to add a box</p>
      </div>
      <div class="modal-actions">
        <button class="primary" id="doneAnnotate">Done</button>
      </div>
    </div>
    <div class="annotator">
      <div class="canvas-wrap"><canvas id="annotationCanvas"></canvas></div>
      <div class="box-panel">
        <div id="bboxStatus" class="bbox-status">No box selected</div>
        <div id="captionModelStatus" class="caption-status hidden"></div>
        <button id="captionBox" class="secondary">Caption selected box</button>
        <button id="clearBoxes" class="secondary">Clear</button>
        <div id="boxList"></div>
      </div>
    </div>
    <div class="modal-footer">
      <button id="skipAllAnnotate" class="danger">Skip all remaining</button>
      <button id="skipAnnotate" class="secondary">Skip image</button>
    </div>
  `;
  return modal;
}
