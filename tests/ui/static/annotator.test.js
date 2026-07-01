import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { showAnnotator } from "../../../prepare_lora_kit/ui/static/steps/bbox_annotation/bbox_annotation.js";
import { isUncaptioned } from "../../../prepare_lora_kit/ui/static/steps/bbox_annotation/bbox-annotation-utils.js";
import { state } from "../../../prepare_lora_kit/ui/static/core/state.js";
import {
  annotationImage,
  annotationPending,
  calls,
  drawBox,
  installMockImage,
  nextTick,
  setCanvasClientRect,
  setupInteractionDom,
} from "./interaction_helpers.js";

let apiCalls;
let contextCalls;

beforeEach(() => {
  ({ apiCalls, contextCalls } = setupInteractionDom());
  installMockImage();
});

function activeCanvas() {
  const layer = document.getElementById("modalLayer");
  const canvas = layer.querySelector("#annotationCanvas");
  setCanvasClientRect(canvas, { left: 10, top: 20, width: 400, height: 300 });
  return canvas;
}

describe("annotation workspace", () => {
  it("draws, edits, captions, clears, and submits a per-image batch", async () => {
    const onSubmitted = calls();
    showAnnotator(annotationPending(), { onSubmitted });

    const layer = document.getElementById("modalLayer");
    const canvas = activeCanvas();
    assert.equal(canvas.width, 400);
    assert.equal(canvas.height, 300);
    assert.equal(layer.querySelector("#captionBox").disabled, true);

    drawBox(canvas, { start: [110, 95], end: [310, 245] });

    assert.equal(layer.querySelectorAll(".box-item").length, 1);
    assert.equal(layer.querySelector(".box-item").classList.contains("selected"), true);
    assert.equal(layer.querySelector("#bboxStatus").textContent, "Selected: Region 1 - prompt label");
    // A per-region thumbnail canvas is rendered for the box.
    assert.equal(layer.querySelectorAll(".box-item .box-thumb").length, 1);

    state.job.caption_status = {
      phase: "loading",
      message: "Loading caption model fake/model",
      model_id: "fake/model",
      adapter: null,
      device: null,
      quantization: "auto",
    };
    global.dispatchEvent(new CustomEvent("plk:job-status", { detail: state.job }));
    assert.match(
      layer.querySelector("#captionModelStatus").textContent,
      /Loading caption model fake\/model/,
    );

    const input = layer.querySelector(".box-item input");
    input.value = "edited label";
    input.dispatchEvent(new window.Event("input", { bubbles: true }));

    layer.querySelector("#captionBox").click();
    await nextTick();

    assert.equal(apiCalls.captioned.length, 1);
    assert.equal(apiCalls.captioned[0].imagePath, "/images/annotate.png");
    assert.deepEqual(apiCalls.captioned[0].box, {
      x1: 0.25,
      y1: 0.25,
      x2: 0.75,
      y2: 0.75,
      label: "edited label",
    });
    assert.equal(layer.querySelector(".box-item input").value, "captioned region");
    assert.match(layer.querySelector(".box-item").textContent, /crop\.png/);

    layer.querySelector("#clearBoxes").click();
    assert.equal(layer.querySelectorAll(".box-item").length, 0);

    drawBox(canvas, { start: [50, 50], end: [54, 54], pointerId: 8 });
    assert.equal(layer.querySelectorAll(".box-item").length, 0);

    drawBox(canvas, { start: [10, 20], end: [210, 170], pointerId: 9 });
    layer.querySelector("#doneAnnotate").click();
    await nextTick();

    assert.deepEqual(apiCalls.submitted, [
      {
        jobId: "job-1",
        requestId: "annotation-1",
        value: {
          images: {
            "/images/annotate.png": {
              annotations: [{ x1: 0, y1: 0, x2: 0.5, y2: 0.5, label: "prompt label" }],
              skipped: false,
            },
          },
          skip_all: false,
        },
      },
    ]);
    assert.equal(onSubmitted.count, 1);
    assert.equal(layer.classList.contains("hidden"), true);
  });

  it("renders a thumbnail per image and switches the active image on click", async () => {
    showAnnotator(
      annotationPending("annotation-nav", [
        annotationImage("first"),
        annotationImage("second"),
      ]),
      { onSubmitted: calls() },
    );

    const layer = document.getElementById("modalLayer");
    assert.equal(layer.querySelectorAll("#thumbStrip .thumb").length, 2);
    assert.equal(
      layer.querySelector('.thumb[data-index="0"]').classList.contains("thumb--current"),
      true,
    );
    // The strip loads the small thumb variant, not the full-resolution uri.
    assert.match(
      layer.querySelector('.thumb[data-index="0"] .thumb__img').getAttribute("src"),
      /w=384$/,
    );

    const canvas = activeCanvas();
    layer.querySelector('.thumb[data-index="1"]').click();
    assert.equal(
      layer.querySelector('.thumb[data-index="1"]').classList.contains("thumb--current"),
      true,
    );

    // A box drawn now belongs to image 2; captioning targets image 2's path.
    drawBox(canvas, { start: [110, 95], end: [310, 245] });
    layer.querySelector("#captionBox").click();
    await nextTick();
    assert.equal(apiCalls.captioned[0].imagePath, "/images/second.png");
  });

  it("keeps each image's boxes and selection isolated across navigation", () => {
    showAnnotator(
      annotationPending("annotation-iso", [
        annotationImage("first"),
        annotationImage("second"),
      ]),
      { onSubmitted: calls() },
    );
    const layer = document.getElementById("modalLayer");
    const canvas = activeCanvas();

    drawBox(canvas, { start: [110, 95], end: [310, 245] });
    assert.equal(layer.querySelectorAll(".box-item").length, 1);

    // Image 2 starts empty.
    layer.querySelector('.thumb[data-index="1"]').click();
    assert.equal(layer.querySelectorAll(".box-item").length, 0);

    // Back to image 1: its box (and selection) are restored.
    layer.querySelector('.thumb[data-index="0"]').click();
    assert.equal(layer.querySelectorAll(".box-item").length, 1);
    assert.equal(layer.querySelector(".box-item").classList.contains("selected"), true);
  });

  it("pre-fills reloaded boxes for already-captioned images", () => {
    showAnnotator(
      annotationPending("annotation-reload", [
        annotationImage("done", {
          done: true,
          annotations: [{ x1: 0.1, y1: 0.1, x2: 0.4, y2: 0.4, label: "a red car" }],
        }),
      ]),
      { onSubmitted: calls() },
    );
    const layer = document.getElementById("modalLayer");
    assert.equal(layer.querySelectorAll(".box-item").length, 1);
    assert.equal(layer.querySelector(".box-item input").value, "a red car");
    assert.equal(
      layer.querySelector('.thumb[data-index="0"]').classList.contains("thumb--done"),
      true,
    );
  });

  it("hides box overlays and blocks drawing while hidden", () => {
    showAnnotator(annotationPending("annotation-hide"), { onSubmitted: calls() });
    const layer = document.getElementById("modalLayer");
    const canvas = activeCanvas();
    drawBox(canvas, { start: [110, 95], end: [310, 245] });

    const before = contextCalls.length;
    layer.querySelector("#hideBoxesToggle").checked = true;
    layer
      .querySelector("#hideBoxesToggle")
      .dispatchEvent(new window.Event("change", { bubbles: true }));

    const since = contextCalls.slice(before);
    assert.ok(since.some((c) => c[0] === "drawImage"));
    assert.ok(!since.some((c) => c[0] === "strokeRect"));

    // Drawing a new box is suppressed while overlays are hidden.
    drawBox(canvas, { start: [20, 20], end: [120, 120], pointerId: 12 });
    assert.equal(layer.querySelectorAll(".box-item").length, 1);
  });

  it("Skip image excludes the current image and advances without submitting", () => {
    showAnnotator(
      annotationPending("annotation-skip", [
        annotationImage("first"),
        annotationImage("second"),
      ]),
      { onSubmitted: calls() },
    );
    const layer = document.getElementById("modalLayer");
    activeCanvas();

    layer.querySelector("#skipAnnotate").click();

    assert.equal(apiCalls.submitted.length, 0);
    assert.equal(
      layer.querySelector('.thumb[data-index="0"]').classList.contains("thumb--skipped"),
      true,
    );
    assert.equal(
      layer.querySelector('.thumb[data-index="1"]').classList.contains("thumb--current"),
      true,
    );
  });

  it("Skip all remaining applies the current image and skips the rest", async () => {
    const onSubmitted = calls();
    showAnnotator(
      annotationPending("annotation-skip-all", [
        annotationImage("first"),
        annotationImage("second"),
      ]),
      { onSubmitted },
    );
    const layer = document.getElementById("modalLayer");
    activeCanvas();

    layer.querySelector("#skipAllAnnotate").click();
    await nextTick();

    assert.deepEqual(apiCalls.submitted[0], {
      jobId: "job-1",
      requestId: "annotation-skip-all",
      value: {
        images: {
          "/images/first.png": { annotations: [], skipped: false },
          "/images/second.png": { annotations: [], skipped: true },
        },
        skip_all: true,
      },
    });
    assert.equal(onSubmitted.count, 1);
  });

  it("locks every interactive control while a caption request is in flight", async () => {
    let release;
    window.pywebview.api.caption_region = () =>
      new Promise((resolve) => {
        release = () => resolve({ caption: "captioned region", crop_path: "/tmp/crop.png" });
      });
    showAnnotator(annotationPending("annotation-lock"), { onSubmitted: calls() });

    const layer = document.getElementById("modalLayer");
    const canvas = activeCanvas();
    drawBox(canvas, { start: [110, 95], end: [310, 245] });

    const locked = [
      "#captionBox",
      "#clearBoxes",
      "#doneAnnotate",
      "#skipAnnotate",
      "#skipAllAnnotate",
      "#modalCancel",
    ];

    layer.querySelector("#captionBox").click();
    await nextTick();

    for (const sel of locked) {
      assert.equal(layer.querySelector(sel).disabled, true, `${sel} disabled`);
    }
    layer
      .querySelectorAll(".box-item button, .box-item input")
      .forEach((el) => assert.equal(el.disabled, true));
    drawBox(canvas, { start: [20, 20], end: [120, 120], pointerId: 11 });
    assert.equal(layer.querySelectorAll(".box-item").length, 1);

    release();
    await nextTick();

    for (const sel of locked) {
      assert.equal(layer.querySelector(sel).disabled, false, `${sel} re-enabled`);
    }
    layer
      .querySelectorAll(".box-item button, .box-item input")
      .forEach((el) => assert.equal(el.disabled, false));
  });

  it("blocks Done and jumps to an image whose region still needs a caption", async () => {
    window.prompt = () => "region 1";
    global.prompt = window.prompt;
    const onSubmitted = calls();
    showAnnotator(
      annotationPending("annotation-missing", [
        annotationImage("first"),
        annotationImage("second"),
      ]),
      { onSubmitted },
    );

    const layer = document.getElementById("modalLayer");
    const canvas = activeCanvas();
    drawBox(canvas, { start: [110, 95], end: [310, 245] });

    // Move to image 2, then try to finish — Done must jump back to image 1.
    layer.querySelector('.thumb[data-index="1"]').click();
    layer.querySelector("#doneAnnotate").click();
    await nextTick();

    assert.equal(apiCalls.submitted.length, 0);
    assert.equal(onSubmitted.count, 0);
    assert.equal(layer.classList.contains("hidden"), false);
    assert.equal(
      layer.querySelector('.thumb[data-index="0"]').classList.contains("thumb--current"),
      true,
    );
    assert.equal(
      layer.querySelector(".box-item").classList.contains("box-item--missing"),
      true,
    );
    assert.match(layer.querySelector("#bboxStatus").textContent, /Caption every region before finishing/);

    // Describing the region clears its glow live.
    const input = layer.querySelector(".box-item input");
    input.value = "a red car";
    input.dispatchEvent(new window.Event("input", { bubbles: true }));
    assert.equal(
      layer.querySelector(".box-item").classList.contains("box-item--missing"),
      false,
    );

    layer.querySelector("#doneAnnotate").click();
    await nextTick();
    assert.equal(apiCalls.submitted.length, 1);
    assert.equal(
      apiCalls.submitted[0].value.images["/images/first.png"].annotations[0].label,
      "a red car",
    );
  });

  it("keeps selected box editable when captioning fails", async () => {
    window.pywebview.api.caption_region = async () => {
      throw new Error("model crashed");
    };
    showAnnotator(annotationPending("annotation-error"), { onSubmitted: calls() });

    const layer = document.getElementById("modalLayer");
    const canvas = activeCanvas();
    drawBox(canvas, { start: [110, 95], end: [310, 245] });

    layer.querySelector("#captionBox").click();
    await nextTick();

    assert.equal(layer.querySelector(".box-item input").value, "prompt label");
    assert.equal(layer.querySelector("#captionBox").disabled, false);
    assert.match(layer.querySelector("#bboxStatus").textContent, /Caption failed: model crashed/);
  });
});

describe("isUncaptioned", () => {
  it("treats blank and placeholder labels as needing a caption", () => {
    assert.equal(isUncaptioned({ label: "" }), true);
    assert.equal(isUncaptioned({ label: "   " }), true);
    assert.equal(isUncaptioned({}), true);
    assert.equal(isUncaptioned({ label: "region 1" }), true);
    assert.equal(isUncaptioned({ label: "Region 12" }), true);
    assert.equal(isUncaptioned({ label: "  region 3  " }), true);
  });

  it("treats real descriptions as captioned", () => {
    assert.equal(isUncaptioned({ label: "a red car" }), false);
    assert.equal(isUncaptioned({ label: "region of interest" }), false);
    assert.equal(isUncaptioned({ label: "region 1 with a hat" }), false);
  });
});
