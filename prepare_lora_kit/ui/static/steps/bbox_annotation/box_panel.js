import { escapeText } from "../../core/dom.js";
import {
  attachShiftStep,
  boxToPixelEdges,
  edgesToNormalizedBox,
  makeField,
} from "./box-panel-utils.js";

// Pixel step applied to a coordinate field while Shift is held.
const SHIFT_STEP = 25;

// Renders the side list of boxes: per-box label input, Left/Top/Right/Bottom
// coordinate fields, and Select/Delete actions.
export class BoxPanel {
  constructor({
    boxList,
    bboxStatus,
    captionBoxButton,
    boxes,
    img,
    getSelected,
    setSelected,
    onChange,
    redraw,
  }) {
    this.boxList = boxList;
    this.bboxStatus = bboxStatus;
    this.captionBoxButton = captionBoxButton;
    this.boxes = boxes;
    this.img = img;
    this.getSelected = getSelected;
    this.setSelected = setSelected;
    this.onChange = onChange;
    this.redraw = redraw;
  }

  // The image's natural pixel size — coordinate fields are shown/edited in
  // original-image pixels, while boxes are stored normalized (0–1).
  imgWidth() {
    return this.img?.naturalWidth || 0;
  }
  imgHeight() {
    return this.img?.naturalHeight || 0;
  }

  // Build the four Left/Top/Right/Bottom inputs for a box. Editing them updates
  // the box geometry and repaints the canvas only (via redraw) — never the full
  // list render — so focus stays put for repeated arrow-key nudges.
  coordFields(box) {
    const wrap = document.createElement("div");
    wrap.className = "box-coords";

    const fields = {
      x1: makeField("L"),
      y1: makeField("T"),
      x2: makeField("R"),
      y2: makeField("B"),
    };

    const syncFromBox = () => {
      const px = boxToPixelEdges(box, this.imgWidth(), this.imgHeight());
      fields.x1.input.value = px.x1;
      fields.y1.input.value = px.y1;
      fields.x2.input.value = px.x2;
      fields.y2.input.value = px.y2;
    };

    const applyFromFields = () => {
      Object.assign(
        box,
        edgesToNormalizedBox(
          {
            x1: fields.x1.input.value,
            y1: fields.y1.input.value,
            x2: fields.x2.input.value,
            y2: fields.y2.input.value,
          },
          this.imgWidth(),
          this.imgHeight(),
        ),
      );
      syncFromBox();
      this.redraw?.();
    };

    for (const [key, field] of Object.entries(fields)) {
      field.input.max =
        key === "x1" || key === "x2" ? this.imgWidth() : this.imgHeight();
      field.input.addEventListener("input", applyFromFields);
      attachShiftStep(field.input, SHIFT_STEP);
      wrap.appendChild(field.cell);
    }
    syncFromBox();
    return wrap;
  }

  // Update the status line + caption button without rebuilding the list, so a
  // focused input survives the change.
  renderStatus() {
    const selected = this.getSelected();
    const selectedBox = this.boxes[selected];
    const selectedBoxLabel = selectedBox?.label ? ` - ${selectedBox.label}` : "";
    this.bboxStatus.textContent = selectedBox
      ? `Selected: Region ${selected + 1}${selectedBoxLabel}`
      : "No box selected";
    this.captionBoxButton.disabled = selected < 0;
  }

  render() {
    const { boxList, boxes } = this;
    const selected = this.getSelected();
    this.renderStatus();
    boxList.replaceChildren();
    boxes.forEach((box, index) => {
      const item = document.createElement("div");
      item.className = `box-item${index === selected ? " selected" : ""}`;
      item.innerHTML = `
        <strong>Region ${index + 1}</strong>
        <input value="${escapeText(box.label || "")}" placeholder="Description" />
        ${box.crop_name ? `<small>${escapeText(box.crop_name)}</small>` : ""}
        <button class="secondary">Select</button>
        <button class="danger">Delete</button>
      `;
      const input = item.querySelector("input");
      // Update the box label in place: repaint the canvas + status only, never
      // re-render the list, otherwise this input would be torn out from under
      // the cursor on every keystroke.
      input.addEventListener("input", () => {
        box.label = input.value;
        this.renderStatus();
        this.redraw?.();
      });
      item.querySelector(".secondary").addEventListener("click", () => {
        this.setSelected(index);
        this.onChange();
      });
      item.querySelector(".danger").addEventListener("click", () => {
        boxes.splice(index, 1);
        this.setSelected(-1);
        this.onChange();
      });
      // Insert the coordinate fields right after the label input.
      item.insertBefore(this.coordFields(box), input.nextSibling);
      boxList.appendChild(item);
    });
  }
}
