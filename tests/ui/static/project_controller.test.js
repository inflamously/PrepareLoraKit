import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { JSDOM } from "jsdom";

import { state } from "../../../prepare_lora_kit/ui/static/core/state.js";
import {
  loadProject,
  selectPending,
} from "../../../prepare_lora_kit/ui/static/project/controller.js";
import { selectedSubstepMap } from "../../../prepare_lora_kit/ui/static/project/selection.js";

let loadProjectCalls;
let projectsByName;

beforeEach(() => {
  const dom = new JSDOM(`<!doctype html><body>
    <div id="app"></div>
    <p id="projectSummary"></p>
    <div id="stepList"></div>
    <select id="projectSelect"><option value="sample" selected>sample</option></select>
    <select id="captionModelPreset">
      <option value="">Select model</option>
      <option value="Qwen/Qwen2-VL-7B-Instruct">Qwen2-VL 7B</option>
      <option value="Qwen/Qwen2.5-VL-3B-Instruct">Qwen2.5-VL 3B</option>
      <option value="custom">Custom</option>
    </select>
    <input id="captionModelCustom" value="" />
    <select id="captionModelTask">
      <option value="auto">Auto</option>
      <option value="image-text-to-text">Image + text to text</option>
      <option value="image-to-text">Image to text</option>
    </select>
    <select id="captionVramMode">
      <option value="auto">Auto</option>
      <option value="4bit">4-bit</option>
      <option value="8bit">8-bit</option>
      <option value="none">Unquantized</option>
    </select>
    <button id="cancelButton"></button>
    <div id="currentStepLabel"></div>
    <p id="jobSummary"></p>
    <pre id="logOutput"></pre>
    <button id="openOutput"></button>
    <button id="runButton"></button>
    <input id="inputDir" value="/images" />
    <input id="outputDir" value="" />
    <input id="tokenInput" value="" />
    <input id="forceInput" type="checkbox" />
  </body>`);
  global.window = dom.window;
  global.document = dom.window.document;
  global.getSelection = () => ({ isCollapsed: true });

  loadProjectCalls = [];
  state.projects = ["sample"];
  state.project = project("sample", [
    step("ImportStep", "pending", false),
    step("QualityGateStep", "pending", false),
    step("CurateStep", "done", false),
    step("UpscaleStep", "pending", true),
    step("VaeGateStep", "pending", false),
  ]);
  projectsByName = new Map([
    ["sample", state.project],
  ]);
  state.selectedSteps = new Set(["UpscaleStep"]);
  state.selectedSubsteps = new Map([
    ["UpscaleStep", new Set(["s3_1_select_candidates"])],
  ]);
  state.jobId = null;
  state.job = null;
  state.handledRequestId = null;
  state.runStarting = false;
  state.outputDir = "";
  state.outputCustomized = false;
  state.mockRuntime = false;
  state.mockProjectName = null;
  state.mockCurateCoverage = "auto";
  global.pywebview = {
    api: {
      load_project: async (projectName, outputDir) => {
        loadProjectCalls.push({ projectName, outputDir });
        const loadedProject = projectsByName.get(projectName) || state.project;
        return {
          project: loadedProject,
          project_name: projectName,
          input_dir: `/images/${projectName}`,
          output_dir: `/outputs/${projectName}`,
        };
      },
    },
  };
});

describe("project controller selection", () => {
  it("defaults to active non-optional steps on project load", async () => {
    state.selectedSteps = new Set();

    await loadProject();

    assert.deepEqual([...state.selectedSteps], [
      "ImportStep",
      "QualityGateStep",
      "CurateStep",
      "VaeGateStep",
    ]);
    assert.deepEqual(selectedSubstepMap(), {
      ImportStep: ["s0_import"],
      QualityGateStep: ["s1_1_score", "s1_2_decide"],
      CurateStep: ["s2_1_dupecheck"],
      VaeGateStep: ["s4_1_reconstruct"],
    });
  });

  it("resets to active non-optional steps only", () => {
    selectPending();

    assert.deepEqual([...state.selectedSteps], [
      "ImportStep",
      "QualityGateStep",
      "CurateStep",
      "VaeGateStep",
    ]);
    assert.deepEqual(selectedSubstepMap().QualityGateStep, [
      "s1_1_score",
      "s1_2_decide",
    ]);
  });

  it("resets project-scoped session state on explicit project change", async () => {
    projectsByName.set(
      "other",
      project("other", [
        step("ImportStep", "pending", false),
        step("CaptionStep", "pending", false, {
          qwen_model_id: "Qwen/Qwen2.5-VL-3B-Instruct",
          vram_tier: "mid",
        }),
        step("UpscaleStep", "pending", true),
      ]),
    );
    appendProjectOption("other");
    document.getElementById("projectSelect").value = "other";
    document.getElementById("outputDir").value = "/outputs/old-custom";
    document.getElementById("tokenInput").value = "old-token";
    document.getElementById("forceInput").checked = true;
    document.getElementById("logOutput").textContent = "old log";
    state.outputDir = "/outputs/old-custom";
    state.outputCustomized = true;
    state.selectedSteps = new Set(["UpscaleStep"]);
    state.selectedSubsteps = new Map([
      ["UpscaleStep", new Set(["s3_1_select_candidates"])],
    ]);
    state.jobId = "finished-job";
    state.job = {
      status: "completed",
      current_step: null,
      logs: ["old log"],
      result: { output_dir: "/outputs/old-custom" },
    };
    state.handledRequestId = "request-1";

    await loadProject({ resetSession: true });

    assert.deepEqual(loadProjectCalls.at(-1), {
      projectName: "other",
      outputDir: null,
    });
    assert.equal(document.getElementById("outputDir").value, "/outputs/other");
    assert.equal(state.outputDir, "/outputs/other");
    assert.equal(state.outputCustomized, false);
    assert.deepEqual([...state.selectedSteps], ["ImportStep", "CaptionStep"]);
    assert.deepEqual(selectedSubstepMap(), {
      ImportStep: ["s0_import"],
      CaptionStep: ["s5_1_caption"],
    });
    assert.equal(document.getElementById("tokenInput").value, "");
    assert.equal(document.getElementById("forceInput").checked, false);
    assert.equal(state.jobId, null);
    assert.equal(state.job, null);
    assert.equal(state.handledRequestId, null);
    assert.equal(document.getElementById("logOutput").textContent, "");
    assert.equal(document.getElementById("openOutput").disabled, true);
  });

  it("preserves selected steps and custom output when requested", async () => {
    document.getElementById("outputDir").value = "/outputs/custom";
    state.outputDir = "/outputs/custom";
    state.outputCustomized = true;
    state.selectedSteps = new Set(["UpscaleStep"]);

    await loadProject({ preserveSelection: true });

    assert.deepEqual(loadProjectCalls.at(-1), {
      projectName: "sample",
      outputDir: "/outputs/custom",
    });
    assert.equal(document.getElementById("outputDir").value, "/outputs/custom");
    assert.equal(state.outputCustomized, true);
    assert.deepEqual([...state.selectedSteps], ["UpscaleStep"]);
  });

  it("resets caption controls to base defaults when project has no caption config", async () => {
    document.getElementById("captionModelPreset").value = "custom";
    document.getElementById("captionModelCustom").value = "custom/model";
    document.getElementById("captionModelTask").value = "image-to-text";
    document.getElementById("captionVramMode").value = "8bit";

    await loadProject();

    assert.equal(
      document.getElementById("captionModelPreset").value,
      "",
    );
    assert.equal(document.getElementById("captionModelCustom").value, "");
    assert.equal(document.getElementById("captionModelTask").value, "auto");
    assert.equal(document.getElementById("captionVramMode").value, "auto");
  });
});

function project(name, steps) {
  return {
    name,
    network: "flux-klein-9b",
    network_type: null,
    steps,
  };
}

function step(type, status, optional, config = {}) {
  const substeps = {
    ImportStep: [{ id: "s0_import", label: "Import", enabled: true, status, prerequisites: [], optional: false }],
    QualityGateStep: [
      { id: "s1_1_score", label: "Score", enabled: true, status, prerequisites: [], optional: false },
      { id: "s1_2_decide", label: "Decide", enabled: true, status, prerequisites: ["s1_1_score"], optional: false },
    ],
    CurateStep: [{ id: "s2_1_dupecheck", label: "Dupe", enabled: true, status, prerequisites: [], optional: false }],
    UpscaleStep: [{ id: "s3_1_select_candidates", label: "Select", enabled: true, status, prerequisites: [], optional: false }],
    VaeGateStep: [{ id: "s4_1_reconstruct", label: "Reconstruct", enabled: true, status, prerequisites: [], optional: false }],
    CaptionStep: [{ id: "s5_1_caption", label: "Caption", enabled: true, status, prerequisites: [], optional: false }],
  };
  return {
    type,
    status,
    optional,
    prerequisites: [],
    config,
    substeps: substeps[type] || [],
  };
}

function appendProjectOption(name) {
  const option = document.createElement("option");
  option.value = name;
  option.textContent = name;
  document.getElementById("projectSelect").append(option);
}
