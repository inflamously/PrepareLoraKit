import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { JSDOM } from "jsdom";

import { state } from "../../../prepare_lora_kit/ui/static/core/state.js";
import { renderSteps } from "../../../prepare_lora_kit/ui/static/project/view.js";

function step(type, extra = {}) {
  return {
    type,
    status: "pending",
    optional: type === "UpscaleStep",
    prerequisites: [],
    config: {},
    substeps: [],
    ...extra,
  };
}

beforeEach(() => {
  const dom = new JSDOM(`<!doctype html><body>
    <p id="projectSummary"></p>
    <div id="stepList"></div>
  </body>`);
  global.window = dom.window;
  global.document = dom.window.document;

  state.inputDir = "/images";
  state.job = null;
  state.runStarting = false;
  state.selectedSteps = new Set();
  state.selectedSubsteps = new Map();
  state.collapsedSteps = new Set();
});

describe("step list attention highlight", () => {
  it("glows the UpscaleStep row when the dataset needs attention", () => {
    state.project = {
      name: "sample",
      network: "flux-klein-9b",
      network_type: null,
      steps: [
        step("CurateStep"),
        step("UpscaleStep", {
          needs_attention: true,
          attention: { recommended: true, undersized: 3, jpeg: 5, scanned: 20 },
        }),
      ],
    };

    renderSteps();

    const rows = [...document.querySelectorAll(".nf-step")];
    const upscale = rows.find((r) => r.querySelector(".nf-step__meta").textContent.includes("UpscaleStep"));
    const curate = rows.find((r) => r.querySelector(".nf-step__meta").textContent.includes("CurateStep"));

    assert.equal(upscale.classList.contains("nf-step--attention"), true);
    assert.match(upscale.getAttribute("title"), /3 images/);
    assert.match(upscale.getAttribute("title"), /5 JPEGs/);
    assert.match(upscale.querySelector(".nf-step__meta").textContent, /recommended/);

    // A step without the flag stays un-highlighted.
    assert.equal(curate.classList.contains("nf-step--attention"), false);
  });

  it("does not glow when needs_attention is absent or false", () => {
    state.project = {
      name: "sample",
      network: "flux-klein-9b",
      network_type: null,
      steps: [
        step("UpscaleStep", { needs_attention: false, attention: null }),
      ],
    };

    renderSteps();

    const upscale = document.querySelector(".nf-step");
    assert.equal(upscale.classList.contains("nf-step--attention"), false);
    assert.equal(upscale.getAttribute("title"), null);
  });
});
