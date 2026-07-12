import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { JSDOM } from "jsdom";

import { state } from "../../../prepare_lora_kit_ui/static/core/state.js";
import { renderSteps } from "../../../prepare_lora_kit_ui/static/project/view.js";

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

describe("live job completion state", () => {
  it("renders done steps and substeps before the project is reloaded", () => {
    state.project = {
      name: "sample",
      steps: [
        step("QualityGateStep", {
          substeps: [
            { id: "score_images", label: "Score", enabled: true, status: "pending" },
            { id: "review_decisions", label: "Review", enabled: true, status: "pending" },
          ],
        }),
      ],
    };
    state.job = {
      status: "running",
      current_step: null,
      current_substep: null,
      completed_steps: ["QualityGateStep"],
      completed_substeps: {
        QualityGateStep: ["score_images", "review_decisions"],
      },
    };

    renderSteps();

    const statuses = [...document.querySelectorAll(".step-status")].map(
      (element) => element.textContent,
    );
    assert.deepEqual(statuses, ["done", "done", "done"]);
  });

  it("renders invalidated steps and enabled substeps pending", () => {
    state.project = {
      name: "sample",
      steps: [
        step("QualityGateStep", {
          status: "done",
          substeps: [
            { id: "score_images", label: "Score", enabled: true, status: "done" },
            { id: "review_decisions", label: "Review", enabled: false, status: "done" },
          ],
        }),
      ],
    };
    state.job = {
      status: "running",
      current_step: null,
      current_substep: null,
      completed_steps: [],
      completed_substeps: {},
      invalidated_steps: ["QualityGateStep"],
    };

    renderSteps();

    const statuses = [...document.querySelectorAll(".step-status")].map(
      (element) => element.textContent,
    );
    assert.deepEqual(statuses, ["pending", "pending", "disabled"]);
  });
});
