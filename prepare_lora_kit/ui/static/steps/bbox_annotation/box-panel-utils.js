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
