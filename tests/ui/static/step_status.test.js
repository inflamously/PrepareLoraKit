import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { JSDOM } from "jsdom";

import { state } from "../../../prepare_lora_kit_ui/static/core/state.js";
import { renderSteps } from "../../../prepare_lora_kit_ui/static/project/view.js";

function step(type, extra = {}) {
  return {
    type,
    status: "pending",
    status_reason: "",
    optional: false,
    prerequisites: [],
    config: {},
    substeps: [],
    ...extra,
  };
}

function substep(id, extra = {}) {
  return { id, label: id, enabled: true, status: "pending", prerequisites: [], optional: false, ...extra };
}

function statusOf(type) {
  const row = [...document.querySelectorAll("#stepList > .nf-step")].find((r) =>
    r.querySelector(".nf-step__meta").textContent.includes(type),
  );
  return row.querySelector(":scope > .step-status").textContent;
}

function substepStatuses(type) {
  const row = [...document.querySelectorAll("#stepList > .nf-step")].find((r) =>
    r.querySelector(".nf-step__meta").textContent.includes(type),
  );
  return [...row.querySelectorAll(".substep")].map((el) => el.querySelector(".step-status").textContent);
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
  state.project = { name: "sample", steps: [step("CurateStep")] };
});

describe("step status badges", () => {
  it("shows live progress from the job while a run is in flight", () => {
    state.job = {
      status: "running",
      current_step: null,
      completed_steps: ["CurateStep"],
      completed_substeps: {},
    };

    renderSteps();

    assert.equal(statusOf("CurateStep"), "done");
  });

  it("ignores a finished job's progress and trusts the persisted status", () => {
    // The reports folder and .plk_state.json were wiped between runs: the
    // backend now reports "pending", and a stale overlay must not override it.
    state.job = {
      status: "completed",
      current_step: null,
      completed_steps: ["CurateStep"],
      completed_substeps: { CurateStep: ["duplicate_check"] },
    };
    state.project = {
      name: "sample",
      steps: [step("CurateStep", { substeps: [substep("duplicate_check")] })],
    };

    renderSteps();

    assert.equal(statusOf("CurateStep"), "pending");
    assert.deepEqual(substepStatuses("CurateStep"), ["pending"]);
  });

  it("warns on a step whose report is gone, with the reason as a tooltip", () => {
    state.project = {
      name: "sample",
      steps: [
        step("CurateStep", {
          status: "stale",
          status_reason: "reports/CurateStep_report.json is missing — re-run this step",
        }),
      ],
    };

    renderSteps();

    const badge = document.querySelector("#stepList > .nf-step > .step-status");
    assert.equal(badge.textContent, "stale");
    assert.equal(badge.classList.contains("nf-pill--warning"), true);
    assert.match(badge.getAttribute("title"), /CurateStep_report\.json is missing/);
  });

  it("badges an optional step that has never run as optional, not pending", () => {
    state.project = {
      name: "sample",
      steps: [step("UpscaleStep", { optional: true })],
    };

    renderSteps();

    const badge = document.querySelector("#stepList > .nf-step > .step-status");
    assert.equal(badge.textContent, "optional");
    assert.equal(badge.classList.contains("nf-pill--optional"), true);
    // The meta line no longer repeats it — the badge is the single carrier.
    assert.doesNotMatch(
      document.querySelector(".nf-step__meta").textContent,
      /optional/i,
    );
  });

  it("still badges an optional step once it has a real status", () => {
    state.project = {
      name: "sample",
      steps: [step("UpscaleStep", { optional: true, status: "done" })],
    };

    renderSteps();

    const badge = document.querySelector("#stepList > .nf-step > .step-status");
    assert.equal(badge.textContent, "done");
    assert.equal(badge.classList.contains("nf-pill--done"), true);
  });

  it("renders a step that reported no work as skipped, with the reason as a tooltip", () => {
    state.project = {
      name: "sample",
      steps: [
        step("CurateStep", {
          status: "skipped",
          status_reason: "no images",
          substeps: [substep("duplicate_check", { status: "skipped" })],
        }),
      ],
    };

    renderSteps();

    assert.equal(statusOf("CurateStep"), "skipped");
    const badge = document.querySelector("#stepList > .nf-step > .step-status");
    assert.equal(badge.getAttribute("title"), "no images");
    assert.deepEqual(substepStatuses("CurateStep"), ["skipped"]);
  });
});
