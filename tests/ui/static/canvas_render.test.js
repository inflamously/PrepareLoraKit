import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { dimOutsideBox } from "../../../prepare_lora_kit_ui/static/steps/bbox_annotation/canvas-render.js";

// Minimal 2D-context stub that records fillStyle + fillRect calls.
function stubContext() {
  const rects = [];
  let fillStyle = null;
  return {
    rects,
    get fillStyle() {
      return fillStyle;
    },
    set fillStyle(value) {
      fillStyle = value;
    },
    fillRect: (...args) => rects.push({ style: fillStyle, args }),
  };
}

describe("dimOutsideBox", () => {
  it("fills the four bands around the selected region with the scrim", () => {
    const ctx = stubContext();

    dimOutsideBox(ctx, { x1: 0.25, y1: 0.5, x2: 0.75, y2: 1 }, 400, 300);

    assert.deepEqual(
      ctx.rects.map((r) => r.args),
      [
        [0, 0, 400, 150], // above
        [0, 300, 400, 0], // below (box reaches the bottom edge)
        [0, 150, 100, 150], // left
        [300, 150, 100, 150], // right
      ],
    );
    assert.ok(ctx.rects.every((r) => /^rgba\(0,0,0,0\.\d+\)$/.test(r.style)));
  });

  it("clamps boxes that spill outside the canvas", () => {
    const ctx = stubContext();

    dimOutsideBox(ctx, { x1: -0.5, y1: -0.2, x2: 1.5, y2: 1.2 }, 200, 100);

    // Fully covering box: every band collapses to zero area.
    assert.deepEqual(
      ctx.rects.map((r) => r.args),
      [
        [0, 0, 200, 0],
        [0, 100, 200, 0],
        [0, 0, 0, 100],
        [200, 0, 0, 100],
      ],
    );
  });
});
