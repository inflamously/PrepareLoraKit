import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import {
  HOVER_DELAY_MS,
  containedImageRect,
  findHoveredPoint,
  showCurateDetails,
} from "../../../prepare_lora_kit/ui/static/steps/curate_details/curate_details.js";
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

  it("shows a thumbnail tooltip after hovering a dot for ~1s", (t) => {
    t.mock.timers.enable({ apis: ["setTimeout"] });
    showCurateDetails(curateDetailsPendingWithPoints(), { onSubmitted: async () => {} });

    const { img, tooltip } = stubCoverageGeometry();
    assert.equal(tooltip.classList.contains("hidden"), true);

    dispatchMouseMove(img, { offsetX: 100, offsetY: 75 }); // point "a" sits at 50%,50% of a 200x150 box
    assert.equal(tooltip.classList.contains("hidden"), true, "not shown before the delay elapses");

    t.mock.timers.tick(HOVER_DELAY_MS - 1);
    assert.equal(tooltip.classList.contains("hidden"), true);

    t.mock.timers.tick(1);
    assert.equal(tooltip.classList.contains("hidden"), false);
    assert.equal(
      tooltip.querySelector(".curate-coverage-tooltip-thumb").getAttribute("src"),
      "http://example.invalid/a.png?w=384",
    );
    assert.match(tooltip.textContent, /a\.png/);

    dispatchMouseMove(img, { offsetX: 0, offsetY: 0 }); // far from every dot
    assert.equal(tooltip.classList.contains("hidden"), true);
  });

  it("cancels the pending tooltip if the cursor moves away before the delay elapses", (t) => {
    t.mock.timers.enable({ apis: ["setTimeout"] });
    showCurateDetails(curateDetailsPendingWithPoints(), { onSubmitted: async () => {} });

    const { img, tooltip } = stubCoverageGeometry();

    dispatchMouseMove(img, { offsetX: 100, offsetY: 75 }); // point "a" at 50%,50%
    t.mock.timers.tick(500);
    dispatchMouseMove(img, { offsetX: 199, offsetY: 149 }); // far from both "a" and "b" (0%,0%)
    t.mock.timers.tick(1000);

    assert.equal(tooltip.classList.contains("hidden"), true);
  });

  it("skips hover wiring entirely when the payload has no points", (t) => {
    t.mock.timers.enable({ apis: ["setTimeout"] });
    showCurateDetails(curateDetailsPending(), { onSubmitted: async () => {} });

    const layer = document.getElementById("modalLayer");
    assert.equal(layer.querySelectorAll(".curate-coverage-tooltip").length, 0);
  });
});

describe("coverage hover geometry", () => {
  it("computes the visible image rect for a letterboxed image", () => {
    const img = { clientWidth: 200, clientHeight: 100, naturalWidth: 100, naturalHeight: 100 };
    assert.deepEqual(containedImageRect(img), { left: 50, top: 0, width: 100, height: 100 });
  });

  it("finds the nearest point within the hit radius, ignoring the letterboxed margin", () => {
    const points = [
      { x_pct: 50, y_pct: 50 },
      { x_pct: 0, y_pct: 0 },
    ];
    const rect = { left: 50, top: 0, width: 100, height: 100 };

    assert.equal(findHoveredPoint(points, 100, 50, rect, 10), points[0]);
    assert.equal(findHoveredPoint(points, 10, 50, rect, 10), null); // outside the rect (letterbox margin)
    assert.equal(findHoveredPoint(points, 100, 90, rect, 10), null); // inside the rect, too far from any point
  });
});

function stubCoverageGeometry() {
  const layer = document.getElementById("modalLayer");
  const img = layer.querySelector(".curate-coverage-frame img");
  for (const prop of ["clientWidth", "clientHeight", "naturalWidth", "naturalHeight"]) {
    Object.defineProperty(img, prop, { value: prop.includes("Width") ? 200 : 150, configurable: true });
  }
  return { img, tooltip: layer.querySelector(".curate-coverage-tooltip") };
}

function dispatchMouseMove(target, { offsetX, offsetY }) {
  const event = new window.Event("mousemove", { bubbles: true, cancelable: true });
  Object.defineProperty(event, "offsetX", { value: offsetX });
  Object.defineProperty(event, "offsetY", { value: offsetY });
  target.dispatchEvent(event);
}

function curateDetailsPendingWithPoints() {
  const pending = curateDetailsPending();
  pending.payload.coverage.points = [
    {
      path: "/images/a.png",
      name: "a.png",
      uri: "http://example.invalid/a.png",
      thumb_uri: "http://example.invalid/a.png?w=384",
      x_pct: 50,
      y_pct: 50,
    },
    {
      path: "/images/b.png",
      name: "b.png",
      uri: "http://example.invalid/b.png",
      x_pct: 0,
      y_pct: 0,
    },
  ];
  return pending;
}

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
