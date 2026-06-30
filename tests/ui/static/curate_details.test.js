import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { showCurateDetails } from "../../../prepare_lora_kit/ui/static/steps/curate_details/curate_details.js";
import {
  calls,
  nextTick,
  setupInteractionDom,
} from "./interaction_helpers.js";

let apiCalls;

beforeEach(() => {
  ({ apiCalls } = setupInteractionDom());
});

describe("curate details interaction", () => {
  it("renders coverage and summary metrics, then confirms", async () => {
    const onSubmitted = calls();
    showCurateDetails(curateDetailsPending(), { onSubmitted });

    const layer = document.getElementById("modalLayer");
    assert.equal(layer.classList.contains("hidden"), false);
    assert.equal(
      layer.querySelector(".curate-coverage img").getAttribute("src"),
      "http://example.invalid/coverage.png",
    );
    assert.match(layer.textContent, /CLIP PCA \+ UMAP/);
    assert.match(layer.textContent, /Kept images/);
    assert.match(layer.textContent, /Dropped duplicates/);

    layer.querySelector("#continueCurateDetails").click();
    await nextTick();

    assert.deepEqual(apiCalls.submitted, [
      {
        jobId: "job-1",
        requestId: "curate-details-1",
        value: { confirmed: true },
      },
    ]);
    assert.equal(onSubmitted.count, 1);
    assert.equal(layer.classList.contains("hidden"), true);
  });

  it("renders a missing coverage state", () => {
    showCurateDetails(
      {
        id: "curate-missing",
        kind: "curate_details",
        payload: {
          report_path: "/reports/CurateStep_report.json",
          coverage_image: null,
          coverage_method: null,
          coverage: {},
          summary: {},
        },
      },
      { onSubmitted: async () => {} },
    );

    const layer = document.getElementById("modalLayer");
    assert.match(layer.textContent, /No coverage image/);
    assert.equal(layer.querySelectorAll(".curate-coverage img").length, 0);
  });

  it("escapes curate detail metadata", () => {
    showCurateDetails(
      {
        id: "curate-escaped",
        kind: "curate_details",
        payload: {
          report_path: "<img onerror=alert(1)>",
          coverage_image: {
            path: "/coverage/plot.png",
            name: "plot.png",
            uri: "http://example.invalid/plot.png",
          },
          coverage_method: "<script>",
          coverage: { method: "<script>", pca_components: 50 },
          summary: { kept_images: 2 },
        },
      },
      { onSubmitted: async () => {} },
    );

    const layer = document.getElementById("modalLayer");
    assert.equal(layer.querySelectorAll("code img").length, 0);
    assert.match(layer.textContent, /<img onerror=alert\(1\)>/);
  });
});

function curateDetailsPending() {
  return {
    id: "curate-details-1",
    kind: "curate_details",
    payload: {
      report_path: "/reports/CurateStep_report.json",
      coverage_image: {
        path: "/reports/coverage.png",
        name: "coverage.png",
        uri: "http://example.invalid/coverage.png",
      },
      coverage_method: "umap",
      coverage: {
        method: "umap",
        preprocess: "pca",
        pca_components: 50,
      },
      summary: {
        kept_images: 12,
        duplicate_pairs: 3,
        dropped_duplicates: 2,
      },
    },
  };
}
