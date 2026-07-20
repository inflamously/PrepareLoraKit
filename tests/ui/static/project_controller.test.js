import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { JSDOM } from "jsdom";

import { state } from "../../../prepare_lora_kit_ui/static/core/state.js";
import {
  collapseAll,
  expandAll,
  loadProject,
  selectPending,
  unselectAll,
} from "../../../prepare_lora_kit_ui/static/project/controller.js";
import { selectedSubstepMap } from "../../../prepare_lora_kit_ui/static/project/selection.js";

let loadProjectCalls;
let projectsByName;

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
    <input id="forceInput" type="checkbox" />
  </body>`);
  global.window = dom.window;
  global.document = dom.window.document;
  global.getSelection = () => ({ isCollapsed: true });

  loadProjectCalls = [];
  state.projects = ["sample"];
  state.activeProject = "sample";
  state.inputDir = "/images";
  state.token = "";
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
    ["UpscaleStep", new Set(["select_upscale_candidates"])],
  ]);
  state.collapsedSteps = new Set();
  state.jobId = null;
  state.job = null;
  state.handledRequestId = null;
  state.runStarting = false;
  state.outputDir = "";
  state.outputCustomized = false;
  state.outputExists = false;
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
          output_exists: false,
        };
      },
      active_job: async () => ({ active: null }),
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
      ImportStep: ["import_images"],
      QualityGateStep: ["score_images", "review_decisions"],
      CurateStep: ["duplicate_check"],
      VaeGateStep: ["reconstruct_images"],
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
      "score_images",
      "review_decisions",
    ]);
  });

  it("clears all selected steps and substeps on unselect all", () => {
    unselectAll();

    assert.deepEqual([...state.selectedSteps], []);
    assert.equal(state.selectedSubsteps.size, 0);
  });

  it("collapses every step then expands them again", () => {
    collapseAll();

    assert.deepEqual([...state.collapsedSteps].sort(), [
      "CurateStep",
      "ImportStep",
      "QualityGateStep",
      "UpscaleStep",
      "VaeGateStep",
    ]);

    expandAll();

    assert.equal(state.collapsedSteps.size, 0);
  });

  it("resets project-scoped session state on explicit project change", async () => {
    projectsByName.set(
      "other",
      project("other", [
        step("ImportStep", "pending", false),
        step("CaptionBboxStep", "pending", false, {
          qwen_model_id: "Qwen/Qwen2.5-VL-3B-Instruct",
          vram_tier: "mid",
        }),
        step("UpscaleStep", "pending", true),
      ]),
    );
    state.activeProject = "other";
    state.token = "old-token";
    document.getElementById("forceInput").checked = true;
    document.getElementById("logOutput").textContent = "old log";
    state.outputDir = "/outputs/old-custom";
    state.outputCustomized = true;
    state.selectedSteps = new Set(["UpscaleStep"]);
    state.selectedSubsteps = new Map([
      ["UpscaleStep", new Set(["select_upscale_candidates"])],
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
    assert.equal(state.outputDir, "/outputs/other");
    assert.equal(state.outputCustomized, false);
    assert.deepEqual([...state.selectedSteps], ["ImportStep", "CaptionBboxStep"]);
    assert.deepEqual(selectedSubstepMap(), {
      ImportStep: ["import_images"],
      CaptionBboxStep: ["caption_images"],
    });
    assert.equal(state.token, "");
    assert.equal(document.getElementById("forceInput").checked, false);
    assert.equal(state.jobId, null);
    assert.equal(state.job, null);
    assert.equal(state.handledRequestId, null);
    assert.equal(document.getElementById("logOutput").textContent, "");
    assert.equal(document.getElementById("openOutput").disabled, true);
  });

  it("preserves selected steps and custom output when requested", async () => {
    state.outputDir = "/outputs/custom";
    state.outputCustomized = true;
    state.selectedSteps = new Set(["UpscaleStep"]);

    await loadProject({ preserveSelection: true });

    assert.deepEqual(loadProjectCalls.at(-1), {
      projectName: "sample",
      outputDir: "/outputs/custom",
    });
    assert.equal(state.outputDir, "/outputs/custom");
    assert.equal(state.outputCustomized, true);
    assert.deepEqual([...state.selectedSteps], ["UpscaleStep"]);
  });
});

function project(name, steps) {
  return {
    name,
    steps,
  };
}

function step(type, status, optional, config = {}) {
  const substeps = {
    ImportStep: [{ id: "import_images", label: "Import", enabled: true, status, prerequisites: [], optional: false }],
    QualityGateStep: [
      { id: "score_images", label: "Score", enabled: true, status, prerequisites: [], optional: false },
      { id: "review_decisions", label: "Decide", enabled: true, status, prerequisites: ["score_images"], optional: false },
    ],
    CurateStep: [{ id: "duplicate_check", label: "Dupe", enabled: true, status, prerequisites: [], optional: false }],
    UpscaleStep: [{ id: "select_upscale_candidates", label: "Select", enabled: true, status, prerequisites: [], optional: false }],
    VaeGateStep: [{ id: "reconstruct_images", label: "Reconstruct", enabled: true, status, prerequisites: [], optional: false }],
    CaptionBboxStep: [{ id: "caption_images", label: "Caption", enabled: true, status, prerequisites: [], optional: false }],
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
