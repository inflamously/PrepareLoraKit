import { api } from "../../core/api.js";
import { state } from "../../+state/index.js";
import { renderCaptionStatus } from "../../caption/status.js";
import { closeModal, modalCancelButton, showModal } from "../../components/modal.js";
import { BoxPanel } from "./box_panel.js";
import { AnnotationCanvas } from "./canvas.js";
import { ThumbnailStrip } from "./thumbnail_strip.js";
import { annotatorModal, isUncaptioned } from "./bbox-annotation-utils.js";
import {
  buildSubmitValue,
  createImageStates,
  firstUncaptionedIndex,
} from "./batch.js";

// Entry point kept as a function to match its sibling step handlers
// (showSourceReview, showVaeReview, …) in job/controller.js.
export function showAnnotator(pending, { onSubmitted }) {
  new Annotator(pending, onSubmitted).show();
}

// Drives the multi-image "Annotate Regions" workspace: holds per-image state,
// repoints the canvas + side panel as the user navigates the thumbnail strip,
// captions regions on demand, and submits the whole batch in one interaction.
class Annotator {
  constructor(pending, onSubmitted) {
    this.pending = pending;
    this.onSubmitted = onSubmitted;
    this.states = createImageStates(pending.payload);
    this.activeIndex = 0;
    this.busy = false;
    this.hideBoxes = false;
    // One reused full-res Image: only the active image is decoded at a time, so
    // memory stays bounded regardless of batch size.
    this.img = new Image();

    const modal = annotatorModal(this.states.length);
    this.modal = modal;
    this.bboxStatus = modal.querySelector("#bboxStatus");
    this.captionModelStatus = modal.querySelector("#captionModelStatus");
    this.captionBoxButton = modal.querySelector("#captionBox");

    globalThis.addEventListener("plk:job-status", this.renderModalCaptionStatus);
    renderCaptionStatus(this.captionModelStatus, state.job?.caption_status);

    this.canvasController = new AnnotationCanvas({
      canvas: modal.querySelector("#annotationCanvas"),
      img: this.img,
      boxes: this.activeState().boxes,
      getSelected: () => this.activeState().selected,
      setSelected: (index) => {
        this.activeState().selected = index;
      },
      getBusy: () => this.busy,
      getHighlightMissing: () => this.activeState().highlightMissing,
      onBoxesChanged: this.refresh,
      onEdit: this.markActiveDirty,
    });

    this.boxPanel = new BoxPanel({
      boxList: modal.querySelector("#boxList"),
      bboxStatus: this.bboxStatus,
      captionBoxButton: this.captionBoxButton,
      boxes: this.activeState().boxes,
      img: this.img,
      getSelected: () => this.activeState().selected,
      setSelected: (index) => {
        this.activeState().selected = index;
      },
      getBusy: () => this.busy,
      getHighlightMissing: () => this.activeState().highlightMissing,
      onChange: this.refresh,
      onEdit: this.markActiveDirty,
      redraw: () => this.canvasController.draw(),
    });

    this.strip = new ThumbnailStrip({
      container: modal.querySelector("#thumbStrip"),
      states: this.states,
      getBusy: () => this.busy,
      onSelect: (index) => this.setActive(index),
    });

    this.wireEvents();
  }

  activeState() {
    return this.states[this.activeIndex];
  }

  show() {
    this.img.onload = this.onActiveImageLoaded;
    showModal(this.modal);
    this.strip.render();
    this.setActive(0);
  }

  // Switch the workspace to a different image: repoint the controllers at that
  // image's boxes and swap the shared <img> source (which repaints on load).
  setActive(index) {
    if (index < 0 || index >= this.states.length) return;
    this.activeIndex = index;
    const s = this.activeState();
    this.canvasController.setActive(this.img, s.boxes);
    this.boxPanel.setActive(this.img, s.boxes);
    this.strip.setActive(index);
    this.img.onload = this.onActiveImageLoaded;
    // Use the downscaled view variant for the canvas: boxes are normalized and crops are taken
    // server-side from the original, so display resolution never affects caption quality.
    this.img.src = s.viewUri || s.uri;
    // Cached/synchronous loads may not fire onload — paint immediately.
    if (this.img.complete) this.onActiveImageLoaded();
  }

  onActiveImageLoaded = () => {
    this.activeState().loaded = true;
    this.canvasController.resizeToImage();
  };

  refresh = () => {
    this.boxPanel?.render();
    this.canvasController?.draw();
    this.strip?.refreshState(this.activeIndex);
  };

  // The user mutated the active image's boxes (drew/edited/deleted/captioned), so
  // mark it for (re)captioning and clear any explicit skip.
  markActiveDirty = () => {
    const s = this.activeState();
    s.dirty = true;
    s.skipped = false;
    this.strip?.refreshState(this.activeIndex);
  };

  // Block a submit that left regions un-captioned on an image that will be
  // captioned: jump to it, turn on its highlight, repaint, then show the message.
  flagMissingCaptions(index, count) {
    this.setActive(index);
    this.activeState().highlightMissing = true;
    this.refresh();
    this.bboxStatus.textContent = `Caption every region before finishing — ${count} region${
      count === 1 ? "" : "s"
    } still need a description.`;
    this.bboxStatus.classList.add("bbox-status--error");
  }

  renderModalCaptionStatus = (event) => {
    renderCaptionStatus(this.captionModelStatus, event.detail?.caption_status);
  };

  cleanup() {
    this.canvasController.cleanup();
    this.strip.cleanup();
    globalThis.removeEventListener("plk:job-status", this.renderModalCaptionStatus);
  }

  async submitAnnotator(value) {
    this.cleanup();
    await api().submit_interaction(state.jobId, this.pending.id, value);
    closeModal();
    await this.onSubmitted();
  }

  // Lock the whole modal while a caption request is in flight.
  setBusy(busy) {
    this.busy = busy;
    for (const id of [
      "captionBox",
      "clearBoxes",
      "doneAnnotate",
      "skipAnnotate",
      "skipAllAnnotate",
      "hideBoxesToggle",
    ]) {
      const el = this.modal.querySelector(`#${id}`);
      if (el) el.disabled = busy;
    }
    if (this.cancelButton) this.cancelButton.disabled = busy;
    this.boxPanel.setBusy(busy);
    this.strip.setBusy(busy);
  }

  async captionSelected() {
    const active = this.activeState();
    const { boxes } = active;
    const { selected } = active;
    const { captionBoxButton } = this;
    if (selected < 0) return alert("Select a box first.");
    this.setBusy(true);
    captionBoxButton.textContent = "Captioning...";
    let errorMessage = "";
    try {
      const result = await api().caption_region(
        state.jobId,
        active.path,
        boxes[selected],
      );
      boxes[selected].label = result.caption || boxes[selected].label;
      if (result.crop_path) boxes[selected].crop_path = result.crop_path;
      if (result.crop_name) boxes[selected].crop_name = result.crop_name;
      if (result.sidecar_path) boxes[selected].sidecar_path = result.sidecar_path;
      this.markActiveDirty();
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
      const boxes = this.activeState().boxes;
      boxes.splice(0, boxes.length);
      this.activeState().selected = -1;
      this.markActiveDirty();
      this.refresh();
    });
    modal.querySelector("#hideBoxesToggle").addEventListener("change", (event) => {
      this.hideBoxes = Boolean(event.target.checked);
      this.canvasController.setHideBoxes(this.hideBoxes);
      this.canvasController.draw();
    });
    modal.querySelector("#doneAnnotate").addEventListener("click", () => {
      const index = firstUncaptionedIndex(this.states);
      if (index >= 0) {
        const count = this.states[index].boxes.filter(isUncaptioned).length;
        this.flagMissingCaptions(index, count);
        return;
      }
      this.submitAnnotator(buildSubmitValue(this.states, { skipAll: false }));
    });
    // Skip image: exclude the current image from captioning and move on; never
    // submits, so other in-progress images are preserved.
    modal.querySelector("#skipAnnotate").addEventListener("click", () => {
      this.activeState().skipped = true;
      this.activeState().dirty = false;
      this.strip.refreshState(this.activeIndex);
      const next = this.nextIndex();
      if (next !== this.activeIndex) this.setActive(next);
    });
    // Skip all remaining: apply the current image, skip every other untouched
    // image, and finish the step.
    modal.querySelector("#skipAllAnnotate").addEventListener("click", () => {
      const active = this.activeState();
      const missing = active.boxes.filter(isUncaptioned);
      if (missing.length) {
        this.flagMissingCaptions(this.activeIndex, missing.length);
        return;
      }
      this.submitAnnotator(
        buildSubmitValue(this.states, { skipAll: true, activeIndex: this.activeIndex }),
      );
    });

    const actions = modal.querySelector(".modal-actions");
    this.cancelButton = modalCancelButton(async () => {
      this.cleanup();
      await this.onSubmitted();
    });
    actions.insertBefore(this.cancelButton, actions.firstChild);
  }

  // The next image to focus after skipping the current one: prefer a later
  // image still needing work, else stay put.
  nextIndex() {
    for (let i = this.activeIndex + 1; i < this.states.length; i += 1) return i;
    return this.activeIndex;
  }
}
