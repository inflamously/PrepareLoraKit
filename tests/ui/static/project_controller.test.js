import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { JSDOM } from "jsdom";

import { state } from "../../../prepare_lora_kit/ui/static/core/state.js";
import { loadProject, selectPending } from "../../../prepare_lora_kit/ui/static/project/controller.js";

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
  });

  it("selects pending non-optional steps only", () => {
    selectPending();

    assert.deepEqual([...state.selectedSteps], [
      "ImportStep",
      "QualityGateStep",
      "VaeGateStep",
    ]);
  });
});

function step(type, status, optional) {
  return {
    type,
    status,
    optional,
    prerequisites: [],
    config: {},
  };
}
