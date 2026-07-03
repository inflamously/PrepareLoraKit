import {
  canvasPointFromEvent,
  clampRect,
  fitCanvasSize,
  normalizedFromPixels,
} from "./canvas-utils.js";
import { drawBox, drawPendingRect } from "./canvas-render.js";
import { isUncaptioned } from "./bbox-annotation-utils.js";

// Owns the annotation <canvas>: renders the image + boxes and turns pointer
// drags into new normalized boxes. Handlers used as event listeners / img.onload
// are arrow-function fields so they stay bound to the instance and keep a stable
// reference for add/removeEventListener.
export class AnnotationCanvas {
  constructor({
    canvas,
    img,
    boxes,
    getSelected,
    setSelected,
    getBusy,
    getHighlightMissing,
    onBoxesChanged,
    onEdit,
  }) {
    this.canvas = canvas;
    this.img = img;
    this.boxes = boxes;
    this.getSelected = getSelected;
    this.setSelected = setSelected;
    this.getBusy = getBusy;
    this.getHighlightMissing = getHighlightMissing;
    this.onBoxesChanged = onBoxesChanged;
    // Called when the user mutates boxes here (draws a new one) so the workspace
    // can mark the active image dirty. Not fired by resize/navigation redraws.
    this.onEdit = onEdit;
    // When true, the image is shown without any box overlays (and drawing is
    // suppressed) so the user can inspect the raw picture.
    this.hideBoxes = false;

    this.ctx = canvas.getContext("2d");
    this.drawing = null;
    this.activePointerId = null;

    canvas.addEventListener("pointerdown", this.onPointerDown);
    canvas.addEventListener("pointercancel", this.cancelDrawing);
    globalThis.addEventListener("blur", this.cancelDrawing);
  }

  // Point the canvas at a different image's boxes (and image element) when the
  // user navigates the thumbnail strip. The caller redraws afterwards.
  setActive(img, boxes) {
    this.img = img;
    this.boxes = boxes;
  }

  setHideBoxes(hidden) {
    this.hideBoxes = hidden;
  }

  draw = () => {
    const { ctx, canvas, img, boxes, drawing } = this;
    if (!img.complete || !canvas.width || !canvas.height) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    // Hide-boxes mode: show the bare image only.
    if (this.hideBoxes) return;
    const selected = this.getSelected();
    const highlight = this.getHighlightMissing?.();
    boxes.forEach((box, index) =>
      drawBox(
        ctx,
        box,
        index,
        selected,
        canvas.width,
        canvas.height,
        highlight && isUncaptioned(box),
      ),
    );
    if (drawing) drawPendingRect(ctx, drawing);
  };

  resizeToImage = () => {
    const { img, canvas } = this;
    const size = fitCanvasSize(
      img.width,
      img.height,
      globalThis.innerWidth,
      globalThis.innerHeight,
    );
    canvas.width = size.width;
    canvas.height = size.height;
    this.onBoxesChanged();
  };

  cleanup = () => {
    this.detachDragListeners();
    this.canvas.removeEventListener("pointerdown", this.onPointerDown);
    this.canvas.removeEventListener("pointercancel", this.cancelDrawing);
    globalThis.removeEventListener("blur", this.cancelDrawing);
  };

  canvasPoint(event) {
    return canvasPointFromEvent(this.canvas, event);
  }

  finishDrawing() {
    const { drawing, canvas, boxes } = this;
    if (!drawing) return;
    const rect = clampRect(drawing, canvas.width, canvas.height);
    this.drawing = null;
    this.activePointerId = null;
    this.detachDragListeners();
    if (rect.x2 - rect.x1 < 10 || rect.y2 - rect.y1 < 10) {
      this.draw();
      return;
    }
    const label =
      globalThis.prompt("Describe this region", `region ${boxes.length + 1}`) || "";
    boxes.push({
      ...normalizedFromPixels(rect, canvas.width, canvas.height),
      label,
    });
    this.setSelected(boxes.length - 1);
    this.onEdit?.();
    this.onBoxesChanged();
  }

  cancelDrawing = () => {
    this.drawing = null;
    this.activePointerId = null;
    this.detachDragListeners();
    this.draw();
  };

  // While a drag is active we track pointermove/pointerup on the window rather
  // than the canvas. Inside pywebview's webview, canvas pointer capture is not
  // reliably honored, so once the cursor crosses the scrollable .canvas-wrap
  // border the canvas would stop receiving move events and the box froze at the
  // edge. Listening on the window keeps the drag alive anywhere on screen.
  moveDuringDrag = (event) => {
    if (!this.drawing || event.pointerId !== this.activePointerId) return;
    const p = this.canvasPoint(event);
    this.drawing.x2 = p.x;
    this.drawing.y2 = p.y;
    this.draw();
  };

  upDuringDrag = (event) => {
    if (event.pointerId !== this.activePointerId) return;
    this.finishDrawing();
  };

  attachDragListeners() {
    globalThis.addEventListener("pointermove", this.moveDuringDrag);
    globalThis.addEventListener("pointerup", this.upDuringDrag);
  }

  detachDragListeners() {
    globalThis.removeEventListener("pointermove", this.moveDuringDrag);
    globalThis.removeEventListener("pointerup", this.upDuringDrag);
  }

  onPointerDown = (event) => {
    // Block drawing a new box while a caption request is in flight.
    if (this.getBusy?.()) return;
    // Don't let the user draw blind while overlays are hidden.
    if (this.hideBoxes) return;
    if (event.button != null && event.button !== 0) return;
    // Best-effort capture; the window listeners are the real safety net.
    try {
      this.canvas.setPointerCapture(event.pointerId);
    } catch {
      /* capture unsupported — window listeners still keep the drag working */
    }
    this.activePointerId = event.pointerId;
    const p = this.canvasPoint(event);
    this.drawing = { x1: p.x, y1: p.y, x2: p.x, y2: p.y };
    this.attachDragListeners();
  };
}
