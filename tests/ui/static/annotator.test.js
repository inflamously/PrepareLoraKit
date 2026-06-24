import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { showAnnotator } from "../../../prepare_lora_kit/ui/static/steps/bbox_annotation/bbox_annotation.js";
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
