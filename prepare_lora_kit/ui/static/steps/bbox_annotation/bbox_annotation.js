import { api } from "../../core/api.js";
import { escapeText } from "../../core/dom.js";
import { state } from "../../+state/index.js";
import { renderCaptionStatus } from "../../caption/status.js";
import { closeModal, modalCancelButton, showModal } from "../../components/modal.js";
import { createBoxPanel } from "./box_panel.js";
import { createAnnotationCanvas } from "./canvas.js";

export function showAnnotator(pending, { onSubmitted }) {
  const image = pending.payload;
  const boxes = [];
  let selected = -1;
  const img = new Image();

  const modal = annotatorModal(image);
  const canvas = modal.querySelector("#annotationCanvas");
  const boxList = modal.querySelector("#boxList");
  const bboxStatus = modal.querySelector("#bboxStatus");
  const captionModelStatus = modal.querySelector("#captionModelStatus");
  const captionBoxButton = modal.querySelector("#captionBox");
  const renderModalCaptionStatus = (event) => {
    renderCaptionStatus(captionModelStatus, event.detail?.caption_status);
  };
  globalThis.addEventListener("plk:job-status", renderModalCaptionStatus);
  renderCaptionStatus(captionModelStatus, state.job?.caption_status);

  const getSelected = () => selected;
  const setSelected = (index) => {
    selected = index;
  };

  let canvasController;
  let boxPanel;
  const refresh = () => {
    boxPanel?.render();
    canvasController?.draw();
  };

  canvasController = createAnnotationCanvas({
    canvas,
    img,
    boxes,
    getSelected,
    setSelected,
    onBoxesChanged: refresh,
  });
  boxPanel = createBoxPanel({
    boxList,
    bboxStatus,
    captionBoxButton,
    boxes,
    getSelected,
    setSelected,
    onChange: refresh,
  });

  // Detach the canvas pointer handlers and the global caption-status listener so
  // they don't leak once the modal is gone — runs whether the user continues or
  // cancels the run.
  function cleanup() {
    canvasController.cleanup();
    globalThis.removeEventListener("plk:job-status", renderModalCaptionStatus);
  }

  async function submitAnnotator(value) {
    cleanup();
    await api().submit_interaction(state.jobId, pending.id, value);
    closeModal();
    await onSubmitted();
  }

  captionBoxButton.addEventListener("click", async () => {
    if (selected < 0) return alert("Select a box first.");
    captionBoxButton.disabled = true;
    captionBoxButton.textContent = "Captioning...";
    let errorMessage = "";
    try {
      const result = await api().caption_region(
        state.jobId,
        image.path,
        boxes[selected],
      );
      boxes[selected].label = result.caption || boxes[selected].label;
      if (result.crop_path) boxes[selected].crop_path = result.crop_path;
      if (result.crop_name) boxes[selected].crop_name = result.crop_name;
      if (result.sidecar_path)
        boxes[selected].sidecar_path = result.sidecar_path;
    } catch (err) {
      errorMessage = err?.message || String(err);
    } finally {
      captionBoxButton.textContent = "Caption selected box";
      renderCaptionStatus(captionModelStatus, state.job?.caption_status);
      refresh();
      if (errorMessage) {
        bboxStatus.textContent = `Caption failed: ${errorMessage}`;
      }
    }
  });
  modal.querySelector("#clearBoxes").addEventListener("click", () => {
    boxes.splice(0, boxes.length);
    selected = -1;
    refresh();
  });
  modal.querySelector("#doneAnnotate").addEventListener("click", async () => {
    await submitAnnotator({
      annotations: boxes.filter((box) => (box.label || "").trim()),
      skipped: false,
      skip_all: false,
    });
  });
  modal.querySelector("#skipAnnotate").addEventListener("click", async () => {
    await submitAnnotator({
      annotations: [],
      skipped: true,
      skip_all: false,
    });
  });
  modal
    .querySelector("#skipAllAnnotate")
    .addEventListener("click", async () => {
      await submitAnnotator({
        annotations: [],
        skipped: true,
        skip_all: true,
      });
    });

  const actions = modal.querySelector(".modal-actions");
  actions.insertBefore(
    modalCancelButton(async () => {
      cleanup();
      await onSubmitted();
    }),
    actions.firstChild,
  );

  img.onload = canvasController.resizeToImage;
  img.src = image.uri;
  showModal(modal);
}

function annotatorModal(image) {
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
