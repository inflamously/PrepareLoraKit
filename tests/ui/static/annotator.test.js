import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { showAnnotator } from "../../../prepare_lora_kit/ui/static/steps/bbox_annotation/bbox_annotation.js";
import { isUncaptioned } from "../../../prepare_lora_kit/ui/static/steps/bbox_annotation/bbox-annotation-utils.js";
import { state } from "../../../prepare_lora_kit/ui/static/core/state.js";
import {
  annotationPending,
  calls,
  drawBox,
  installMockImage,
  nextTick,
  setCanvasClientRect,
  setupInteractionDom,
} from "./interaction_helpers.js";

let apiCalls;

beforeEach(() => {
  ({ apiCalls } = setupInteractionDom());
  installMockImage();
});

describe("annotation interaction", () => {
  it("draws, edits, captions, clears, and submits annotations", async () => {
    const onSubmitted = calls();
    showAnnotator(annotationPending(), { onSubmitted });

    const layer = document.getElementById("modalLayer");
    const canvas = layer.querySelector("#annotationCanvas");
    setCanvasClientRect(canvas, { left: 10, top: 20, width: 400, height: 300 });
    assert.equal(canvas.width, 400);
    assert.equal(canvas.height, 300);
    assert.equal(layer.querySelector("#captionBox").disabled, true);

    drawBox(canvas, { start: [110, 95], end: [310, 245] });

    assert.equal(layer.querySelectorAll(".box-item").length, 1);
    assert.equal(layer.querySelector(".box-item").classList.contains("selected"), true);
    assert.equal(layer.querySelector("#bboxStatus").textContent, "Selected: Region 1 - prompt label");
    assert.equal(layer.querySelector("#captionBox").disabled, false);

    state.job.caption_status = {
      phase: "loading",
      message: "Loading caption model fake/model",
      model_id: "fake/model",
      adapter: null,
      device: null,
      quantization: "auto",
    };
    global.dispatchEvent(
      new CustomEvent("plk:job-status", { detail: state.job }),
    );
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
    assert.equal(apiCalls.captioned[0].jobId, "job-1");
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
    assert.equal(layer.querySelector("#bboxStatus").textContent, "No box selected");

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
          annotations: [
            {
              x1: 0,
              y1: 0,
              x2: 0.5,
              y2: 0.5,
              label: "prompt label",
            },
          ],
          skipped: false,
          skip_all: false,
        },
      },
    ]);
    assert.equal(onSubmitted.count, 1);
    assert.equal(layer.classList.contains("hidden"), true);
  });

  it("submits skip payloads for one image or all remaining images", async () => {
    const firstSubmitted = calls();
    showAnnotator(annotationPending("annotation-skip"), { onSubmitted: firstSubmitted });
    document.getElementById("skipAnnotate").click();
    await nextTick();

    assert.deepEqual(apiCalls.submitted[0], {
      jobId: "job-1",
      requestId: "annotation-skip",
      value: {
        annotations: [],
        skipped: true,
        skip_all: false,
      },
    });
    assert.equal(firstSubmitted.count, 1);

    const secondSubmitted = calls();
    showAnnotator(annotationPending("annotation-skip-all"), {
      onSubmitted: secondSubmitted,
    });
    document.getElementById("skipAllAnnotate").click();
    await nextTick();

    assert.deepEqual(apiCalls.submitted[1], {
      jobId: "job-1",
      requestId: "annotation-skip-all",
      value: {
        annotations: [],
        skipped: true,
        skip_all: true,
      },
    });
    assert.equal(secondSubmitted.count, 1);
  });

  it("locks every interactive control while a caption request is in flight", async () => {
    let release;
    window.pywebview.api.caption_region = (jobId, imagePath, box) =>
      new Promise((resolve) => {
        release = () =>
          resolve({ caption: "captioned region", crop_path: "/tmp/crop.png" });
      });
    showAnnotator(annotationPending("annotation-lock"), { onSubmitted: calls() });

    const layer = document.getElementById("modalLayer");
    const canvas = layer.querySelector("#annotationCanvas");
    setCanvasClientRect(canvas, { left: 10, top: 20, width: 400, height: 300 });
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
    // Per-box Select/Delete buttons and the label/coord inputs lock too.
    layer
      .querySelectorAll(".box-item button, .box-item input")
      .forEach((el) => assert.equal(el.disabled, true));
    // Drawing a new box is blocked mid-caption.
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

  it("blocks Done and flags regions still missing a caption", async () => {
    // Keep the auto-filled "region N" placeholder instead of describing the box.
    // canvas.js reads globalThis.prompt, so override the Node global too.
    window.prompt = () => "region 1";
    global.prompt = window.prompt;
    const onSubmitted = calls();
    showAnnotator(annotationPending("annotation-missing"), { onSubmitted });

    const layer = document.getElementById("modalLayer");
    const canvas = layer.querySelector("#annotationCanvas");
    setCanvasClientRect(canvas, { left: 10, top: 20, width: 400, height: 300 });
    drawBox(canvas, { start: [110, 95], end: [310, 245] });

    layer.querySelector("#doneAnnotate").click();
    await nextTick();

    // Nothing submitted and the modal stays open.
    assert.equal(apiCalls.submitted.length, 0);
    assert.equal(onSubmitted.count, 0);
    assert.equal(layer.classList.contains("hidden"), false);
    // The region glows in the list and the status bar shows the error message.
    assert.equal(
      layer.querySelector(".box-item").classList.contains("box-item--missing"),
      true,
    );
    const status = layer.querySelector("#bboxStatus");
    assert.equal(status.classList.contains("bbox-status--error"), true);
    assert.match(status.textContent, /Caption every region before finishing/);

    // Describing the region clears its glow live (no list re-render needed).
    const input = layer.querySelector(".box-item input");
    input.value = "a red car";
    input.dispatchEvent(new window.Event("input", { bubbles: true }));
    assert.equal(
      layer.querySelector(".box-item").classList.contains("box-item--missing"),
      false,
    );

    // Done now submits the captioned region and closes the modal.
    layer.querySelector("#doneAnnotate").click();
    await nextTick();
    assert.equal(apiCalls.submitted.length, 1);
    assert.equal(apiCalls.submitted[0].value.annotations[0].label, "a red car");
    assert.equal(onSubmitted.count, 1);
    assert.equal(layer.classList.contains("hidden"), true);
  });

  it("keeps selected box editable when captioning fails", async () => {
    window.pywebview.api.caption_region = async () => {
      throw new Error("model crashed");
    };
    showAnnotator(annotationPending("annotation-error"), { onSubmitted: calls() });

    const layer = document.getElementById("modalLayer");
    const canvas = layer.querySelector("#annotationCanvas");
    setCanvasClientRect(canvas, { left: 10, top: 20, width: 400, height: 300 });
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
