// Helpers for the box panel, kept out of the BoxPanel class so they stay
// stateless and easy to read/test: coordinate conversions between normalized
// box coords (0–1, the on-disk format) and the original-image pixel values
// shown in the L/T/R/B edit fields, plus the small input builder.

export const clamp01 = (value) => Math.max(0, Math.min(1, value));

// Normalized box -> integer pixel edges for the L/T/R/B inputs.
export function boxToPixelEdges(box, width, height) {
  return {
    x1: Math.round(box.x1 * width),
    y1: Math.round(box.y1 * height),
    x2: Math.round(box.x2 * width),
    y2: Math.round(box.y2 * height),
  };
}

// Pixel edge values (any order, possibly non-numeric) -> ordered, clamped
// normalized box. Keeps left<right and top<bottom regardless of which edge
// was edited.
export function edgesToNormalizedBox(edges, width, height) {
  const w = width || 1;
  const h = height || 1;
  let left = clamp01((parseFloat(edges.x1) || 0) / w);
  let top = clamp01((parseFloat(edges.y1) || 0) / h);
  let right = clamp01((parseFloat(edges.x2) || 0) / w);
  let bottom = clamp01((parseFloat(edges.y2) || 0) / h);
  if (right < left) [left, right] = [right, left];
  if (bottom < top) [top, bottom] = [bottom, top];
  return { x1: left, y1: top, x2: right, y2: bottom };
}

function applyBoundedStepValue(input, dir, step) {
  const min = input.min === "" ? -Infinity : Number(input.min);
  const max = input.max === "" ? Infinity : Number(input.max);
  const prevValue = (Number.parseFloat(input.value) || 0)
  const nextValue = prevValue + dir * step;
  return Math.max(min, Math.min(max, nextValue));
}

// Let Shift+ArrowUp/ArrowDown nudge a number input by `step` (instead of the
// native 1), clamped to its min/max. Dispatches a synthetic input event so the
// field's normal input handler runs and treats it like any other edit.
export function attachShiftStep(input, step) {
  let isShiftPressed = false;
  input.addEventListener("keydown", (event) => {
    isShiftPressed = event.shiftKey
    if (!event.shiftKey) {
      return;
    }
    const dir =
      event.key === "ArrowUp" ? 1 : event.key === "ArrowDown" ? -1 : 0;
    if (!dir) return;
    event.preventDefault();
    input.value = applyBoundedStepValue(input, dir, step);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  input.addEventListener("keyup", (event) => {
    isShiftPressed = event.shiftKey
  })
  input.addEventListener("wheel", (event) => {
    if (document.activeElement !== input) {
      return;
    }
    if (!isShiftPressed) {
      return;
    }
    event.preventDefault();
    const dir = event.deltaY < 0 ? 1 : -1;
    if (Number.isNaN(dir)) {
      return;
    }
    input.value = applyBoundedStepValue(input, dir, step);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  })
}

// Render a small thumbnail of a single box's region by cropping the already
// decoded source image onto a tiny canvas — no backend round-trip. Falls back to
// the element's width/height so the JSDOM test mock (no naturalWidth) still
// exercises the draw call. No-op until the image is decoded.
export function drawCropThumb(canvas, img, box, maxSize = 64) {
  if (!img || !img.complete) return;
  const sw = img.naturalWidth || img.width || 0;
  const sh = img.naturalHeight || img.height || 0;
  if (!sw || !sh) return;

  const sx = clamp01(Math.min(box.x1, box.x2)) * sw;
  const sy = clamp01(Math.min(box.y1, box.y2)) * sh;
  const cw = Math.max(1, Math.abs(box.x2 - box.x1) * sw);
  const ch = Math.max(1, Math.abs(box.y2 - box.y1) * sh);

  const scale = Math.min(maxSize / cw, maxSize / ch, 1);
  const dw = Math.max(1, Math.round(cw * scale));
  const dh = Math.max(1, Math.round(ch * scale));
  canvas.width = dw;
  canvas.height = dh;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, dw, dh);
  ctx.drawImage(img, sx, sy, cw, ch, 0, 0, dw, dh);
}

// Build a single labelled number input (one box edge).
export function makeField(label) {
  const cell = document.createElement("label");
  cell.className = "coord-field";
  cell.textContent = label;
  const input = document.createElement("input");
  input.type = "number";
  input.step = "1";
  input.min = "0";
  cell.appendChild(input);
  return { cell, input };
}
