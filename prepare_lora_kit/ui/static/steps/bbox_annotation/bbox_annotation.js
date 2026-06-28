import { api } from "../../core/api.js";
import { state } from "../../+state/index.js";
import { renderCaptionStatus } from "../../caption/status.js";
import { closeModal, modalCancelButton, showModal } from "../../components/modal.js";
import { BoxPanel } from "./box_panel.js";
import { AnnotationCanvas } from "./canvas.js";
import { annotatorModal, isUncaptioned } from "./bbox-annotation-utils.js";

// Entry point kept as a function to match its sibling step handlers
// (showSourceReview, showVaeReview, …) in job/controller.js.
export function showAnnotator(pending, { onSubmitted }) {
  new Annotator(pending, onSubmitted).show();
}

// Drives the "Annotate Regions" modal: owns the box list + selection, wires the
// canvas and side panel together, and submits/cancels the interaction.
class Annotator {
  constructor(pending, onSubmitted) {
    this.pending = pending;
    this.onSubmitted = onSubmitted;
    this.image = pending.payload;
    this.boxes = [];
    this.selected = -1;
    this.busy = false;
    // Turns on after a Done click that found un-captioned regions, so the canvas
    // and box list glow-highlight the offending frames until they're captioned.
    this.highlightMissing = false;
    this.img = new Image();

    const modal = annotatorModal(this.image);
    this.modal = modal;
    this.bboxStatus = modal.querySelector("#bboxStatus");
    this.captionModelStatus = modal.querySelector("#captionModelStatus");
    this.captionBoxButton = modal.querySelector("#captionBox");

    globalThis.addEventListener("plk:job-status", this.renderModalCaptionStatus);
    renderCaptionStatus(this.captionModelStatus, state.job?.caption_status);

    this.canvasController = new AnnotationCanvas({
      canvas: modal.querySelector("#annotationCanvas"),
      img: this.img,
      boxes: this.boxes,
      getSelected: () => this.selected,
      setSelected: (index) => {
        this.selected = index;
      },
      getBusy: () => this.busy,
      getHighlightMissing: () => this.highlightMissing,
      onBoxesChanged: this.refresh,
    });

    this.boxPanel = new BoxPanel({
      boxList: modal.querySelector("#boxList"),
      bboxStatus: this.bboxStatus,
      captionBoxButton: this.captionBoxButton,
      boxes: this.boxes,
      img: this.img,
      getSelected: () => this.selected,
      setSelected: (index) => {
        this.selected = index;
      },
      getBusy: () => this.busy,
      getHighlightMissing: () => this.highlightMissing,
      onChange: this.refresh,
      redraw: () => this.canvasController.draw(),
    });

    this.wireEvents();
  }

  show() {
    this.img.onload = this.canvasController.resizeToImage;
    this.img.src = this.image.uri;
    showModal(this.modal);
  }

  refresh = () => {
    this.boxPanel?.render();
    this.canvasController?.draw();
  };

  // Blocks a Done click that left regions un-captioned: turn on highlight mode,
  // repaint so the offending frames glow, then set the message — after refresh()
  // so BoxPanel.renderStatus doesn't overwrite it.
  flagMissingCaptions(count) {
    this.highlightMissing = true;
    this.refresh();
    this.bboxStatus.textContent = `Caption every region before finishing — ${count} region${
      count === 1 ? "" : "s"
    } still need a description.`;
    this.bboxStatus.classList.add("bbox-status--error");
  }

  renderModalCaptionStatus = (event) => {
    renderCaptionStatus(this.captionModelStatus, event.detail?.caption_status);
  };

  // Detach the canvas pointer handlers and the global caption-status listener so
  // they don't leak once the modal is gone — runs whether the user continues or
  // cancels the run.
  cleanup() {
    this.canvasController.cleanup();
    globalThis.removeEventListener("plk:job-status", this.renderModalCaptionStatus);
  }

  async submitAnnotator(value) {
    this.cleanup();
    await api().submit_interaction(state.jobId, this.pending.id, value);
    closeModal();
    await this.onSubmitted();
  }

  // Lock the whole modal while a caption request is in flight: every interactive
  // control is disabled except closing the window, then re-enabled when the
  // request finishes. `busy` is the single source of truth the canvas and box
  // panel also read (via getBusy) to block drawing/selection mid-run.
  setBusy(busy) {
    this.busy = busy;
    for (const id of [
      "captionBox",
      "clearBoxes",
      "doneAnnotate",
      "skipAnnotate",
      "skipAllAnnotate",
    ]) {
      const el = this.modal.querySelector(`#${id}`);
      if (el) el.disabled = busy;
    }
    if (this.cancelButton) this.cancelButton.disabled = busy;
    this.boxPanel.setBusy(busy);
  }

  async captionSelected() {
    const { boxes, selected, captionBoxButton } = this;
    if (selected < 0) return alert("Select a box first.");
    this.setBusy(true);
    captionBoxButton.textContent = "Captioning...";
    let errorMessage = "";
    try {
      const result = await api().caption_region(
        state.jobId,
        this.image.path,
        boxes[selected],
      );
      boxes[selected].label = result.caption || boxes[selected].label;
      if (result.crop_path) boxes[selected].crop_path = result.crop_path;
      if (result.crop_name) boxes[selected].crop_name = result.crop_name;
      if (result.sidecar_path) boxes[selected].sidecar_path = result.sidecar_path;
    } catch (err) {
      errorMessage = err?.message || String(err);
    } finally {
      captionBoxButton.textContent = "Caption selected box";
      this.setBusy(false);
      renderCaptionStatus(this.captionModelStatus, state.job?.caption_status);
      this.refresh();
      if (errorMessage) {
        this.bboxStatus.textContent = `Caption failed: ${errorMessage}`;
      }
    }
  }

  wireEvents() {
    const { modal } = this;
    this.captionBoxButton.addEventListener("click", () => this.captionSelected());
    modal.querySelector("#clearBoxes").addEventListener("click", () => {
      this.boxes.splice(0, this.boxes.length);
      this.selected = -1;
      this.refresh();
    });
    modal.querySelector("#doneAnnotate").addEventListener("click", () => {
      const missing = this.boxes.filter(isUncaptioned);
      if (missing.length) {
        this.flagMissingCaptions(missing.length);
        return;
      }
      this.submitAnnotator({
        annotations: this.boxes.filter((box) => (box.label || "").trim()),
        skipped: false,
        skip_all: false,
      });
    });
    modal.querySelector("#skipAnnotate").addEventListener("click", () => {
      this.submitAnnotator({ annotations: [], skipped: true, skip_all: false });
    });
    modal.querySelector("#skipAllAnnotate").addEventListener("click", () => {
      this.submitAnnotator({ annotations: [], skipped: true, skip_all: true });
    });

    const actions = modal.querySelector(".modal-actions");
    this.cancelButton = modalCancelButton(async () => {
      this.cleanup();
      await this.onSubmitted();
    });
    actions.insertBefore(this.cancelButton, actions.firstChild);
  }
}
