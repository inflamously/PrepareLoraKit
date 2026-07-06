import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { showExportReview } from "../../../prepare_lora_kit_ui/static/steps/export_review/export_review.js";
import {
  calls,
  exportReviewPending,
  nextTick,
  setupInteractionDom,
} from "./interaction_helpers.js";

let apiCalls;

beforeEach(() => {
  ({ apiCalls } = setupInteractionDom());
});

describe("export review interaction", () => {
  it("renders added/modified/orphaned sections and the target folder", () => {
    showExportReview(exportReviewPending(), { onSubmitted: async () => {} });

    const layer = document.getElementById("modalLayer");
    assert.equal(layer.classList.contains("hidden"), false);
    assert.match(layer.textContent, /\/data\/input_export/);
    assert.match(layer.textContent, /subject\/image_01\.png/);
    assert.match(layer.textContent, /old_reject\.png/);
    // Orphaned rows are read-only (no checkbox), added/modified are toggleable.
    assert.equal(layer.querySelectorAll("input[type=checkbox][data-rel]").length, 3);
    assert.equal(layer.querySelector(".export-orphaned .export-row input"), null);
  });

  it("confirms with the unchecked files listed as excluded", async () => {
    const onSubmitted = calls();
    showExportReview(exportReviewPending(), { onSubmitted });

    const layer = document.getElementById("modalLayer");
    const checkbox = layer.querySelector('input[data-rel="image_02.png"]');
    checkbox.checked = false;
    checkbox.dispatchEvent(new window.Event("change"));

    layer.querySelector("#confirmExport").click();
    await nextTick();

    assert.deepEqual(apiCalls.submitted, [
      {
        jobId: "job-1",
        requestId: "export-review-1",
        value: { confirmed: true, excluded: ["image_02.png"] },
      },
    ]);
    assert.equal(onSubmitted.count, 1);
    assert.equal(layer.classList.contains("hidden"), true);
  });

  it("skip export resumes the run without writing", async () => {
    const onSubmitted = calls();
    showExportReview(exportReviewPending(), { onSubmitted });

    const layer = document.getElementById("modalLayer");
    layer.querySelector("#skipExport").click();
    await nextTick();

    assert.deepEqual(apiCalls.submitted, [
      {
        jobId: "job-1",
        requestId: "export-review-1",
        value: { confirmed: false, excluded: [] },
      },
    ]);
    assert.equal(onSubmitted.count, 1);
  });

  it("disables Export when there is nothing to write", () => {
    showExportReview(
      {
        id: "export-empty",
        kind: "export_review",
        payload: {
          target_dir: "/data/input_export",
          added: [],
          modified: [],
          orphaned: [],
          counts: { added: 0, modified: 0, unchanged: 5, orphaned: 0 },
        },
      },
      { onSubmitted: async () => {} },
    );

    const layer = document.getElementById("modalLayer");
    assert.equal(layer.querySelector("#confirmExport").disabled, true);
    assert.match(layer.textContent, /Nothing to export/);
  });

  it("escapes untrusted rel paths", () => {
    showExportReview(
      {
        id: "export-escaped",
        kind: "export_review",
        payload: {
          target_dir: "<img onerror=alert(1)>",
          added: [{ rel: "<script>evil</script>.png", path: "/x", name: "x", has_caption: false }],
          modified: [],
          orphaned: [],
          counts: { added: 1, modified: 0, unchanged: 0, orphaned: 0 },
        },
      },
      { onSubmitted: async () => {} },
    );

    const layer = document.getElementById("modalLayer");
    assert.equal(layer.querySelectorAll("script").length, 0);
    assert.match(layer.textContent, /<script>evil<\/script>\.png/);
  });
});
