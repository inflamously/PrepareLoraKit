import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { JSDOM } from "jsdom";

import { state } from "../../../prepare_lora_kit/ui/static/core/state.js";
import { loadProject, selectPending } from "../../../prepare_lora_kit/ui/static/project/controller.js";
import { selectedSubstepMap } from "../../../prepare_lora_kit/ui/static/project/selection.js";

beforeEach(() => {
  const dom = new JSDOM(`<!doctype html><body>
    <div id="app"></div>
    <p id="projectSummary"></p>
    <div id="stepList"></div>
    <select id="projectSelect"><option value="sample" selected>sample</option></select>
    <button id="cancelButton"></button>
    <div id="currentStepLabel"></div>
    <p id="jobSummary"></p>
    <pre id="logOutput"></pre>
    <button id="openOutput"></button>
    <button id="runButton"></button>
    <input id="inputDir" value="/images" />
    <input id="outputDir" value="" />
  </body>`);
  global.window = dom.window;
  global.document = dom.window.document;
  global.getSelection = () => ({ isCollapsed: true });

  state.projects = [];
  state.project = {
    name: "sample",
    network: "flux-klein-9b",
    network_type: null,
    steps: [
      step("ImportStep", "pending", false),
      step("QualityGateStep", "pending", false),
      step("CurateStep", "done", false),
      step("UpscaleStep", "pending", true),
      step("VaeGateStep", "pending", false),
    ],
  };
  state.selectedSteps = new Set(["UpscaleStep"]);
  state.selectedSubsteps = new Map([
    ["UpscaleStep", new Set(["s3_1_select_candidates"])],
  ]);
  state.job = null;
  state.runStarting = false;
  state.outputCustomized = false;
  global.pywebview = {
    api: {
      load_project: async () => ({
        project: state.project,
        project_name: "sample",
        input_dir: "/images",
        output_dir: "/outputs/sample",
      }),
    },
  };
});

describe("project controller selection", () => {
  it("defaults to pending non-optional steps on project load", async () => {
    state.selectedSteps = new Set();

    await loadProject();

    assert.deepEqual([...state.selectedSteps], [
      "ImportStep",
      "QualityGateStep",
      "VaeGateStep",
    ]);
    assert.deepEqual(selectedSubstepMap(), {
      ImportStep: ["s0_import"],
      QualityGateStep: ["s1_1_score", "s1_2_decide"],
      VaeGateStep: ["s4_1_reconstruct"],
    });
  });

  it("selects pending non-optional steps only", () => {
    selectPending();

    assert.deepEqual([...state.selectedSteps], [
      "ImportStep",
      "QualityGateStep",
      "VaeGateStep",
    ]);
    assert.deepEqual(selectedSubstepMap().QualityGateStep, [
      "s1_1_score",
      "s1_2_decide",
    ]);
  });
});

function step(type, status, optional) {
  const substeps = {
    ImportStep: [{ id: "s0_import", label: "Import", enabled: true, status, prerequisites: [], optional: false }],
    QualityGateStep: [
      { id: "s1_1_score", label: "Score", enabled: true, status, prerequisites: [], optional: false },
      { id: "s1_2_decide", label: "Decide", enabled: true, status, prerequisites: ["s1_1_score"], optional: false },
    ],
    CurateStep: [{ id: "s2_1_dupecheck", label: "Dupe", enabled: true, status, prerequisites: [], optional: false }],
    UpscaleStep: [{ id: "s3_1_select_candidates", label: "Select", enabled: true, status, prerequisites: [], optional: false }],
    VaeGateStep: [{ id: "s4_1_reconstruct", label: "Reconstruct", enabled: true, status, prerequisites: [], optional: false }],
  };
  return {
    type,
    status,
    optional,
    prerequisites: [],
    config: {},
    substeps: substeps[type] || [],
  };
}
