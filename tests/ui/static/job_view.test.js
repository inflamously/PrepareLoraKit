import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { JSDOM } from "jsdom";

import { state } from "../../../prepare_lora_kit_ui/static/core/state.js";
import { renderJob } from "../../../prepare_lora_kit_ui/static/job/view.js";
import { openOutput } from "../../../prepare_lora_kit_ui/static/job/controller.js";

const NO_OUTPUT_HINT = "No output folder yet - run the pipeline first";

let openPathCalls;

beforeEach(() => {
  const dom = new JSDOM(`<!doctype html><body>
    <div id="app"></div>
    <button id="cancelButton"></button>
    <div id="currentStepLabel"></div>
    <div id="captionStatusLabel"></div>
    <p id="jobSummary"></p>
    <pre id="logOutput"></pre>
    <button id="openOutput"></button>
    <button id="runButton"></button>
  </body>`);
  global.window = dom.window;
  global.document = dom.window.document;
  global.getSelection = () => ({ isCollapsed: true });

  openPathCalls = [];
  state.job = null;
  state.jobId = null;
  state.runStarting = false;
  state.outputDir = "";
  state.outputExists = false;
  global.pywebview = {
    api: {
      open_path: async (path) => {
        openPathCalls.push(path);
        return { opened: true };
      },
    },
  };
});

function button() {
  return document.getElementById("openOutput");
}

function completedJob(result) {
  return {
    status: "completed",
    current_step: null,
    logs: [],
    caption_status: null,
    cancel_requested: false,
    result,
  };
}

describe("open output button availability", () => {
  it("enables with no job when the output folder already exists on disk", () => {
    state.outputDir = "/outputs/sample";
    state.outputExists = true;

    renderJob();

    assert.equal(button().disabled, false);
    assert.equal(button().title, "");
  });

  it("disables with an explanatory tooltip when the folder does not exist yet", () => {
    state.outputDir = "/outputs/sample";
    state.outputExists = false;

    renderJob();

    assert.equal(button().disabled, true);
    assert.equal(button().title, NO_OUTPUT_HINT);
  });

  it("stays enabled for a failed run whose output folder was partially written", () => {
    state.outputDir = "/outputs/sample";
    state.outputExists = true;
    state.job = { ...completedJob(null), status: "failed" };

    renderJob();

    assert.equal(button().disabled, false);
  });

  it("enables from the job result even before the project reload lands", () => {
    state.outputExists = false;
    state.job = completedJob({ output_dir: "/outputs/sample" });

    renderJob();

    assert.equal(button().disabled, false);
  });
});

describe("open output action", () => {
  it("falls back to the project output path when there is no job result", async () => {
    state.outputDir = "/outputs/sample";
    state.outputExists = true;

    await openOutput();

    assert.deepEqual(openPathCalls, ["/outputs/sample"]);
  });

  it("prefers the completed job result over the project path", async () => {
    state.outputDir = "/outputs/sample";
    state.job = completedJob({ output_dir: "/outputs/from-job" });

    await openOutput();

    assert.deepEqual(openPathCalls, ["/outputs/from-job"]);
  });

  it("does nothing when no output path is known at all", async () => {
    await openOutput();

    assert.deepEqual(openPathCalls, []);
  });

  it("surfaces a backend failure instead of silently swallowing it", async () => {
    state.outputDir = "/outputs/sample";
    global.pywebview.api.open_path = async () => ({
      opened: false,
      error: "Path does not exist: /outputs",
    });
    const alerts = [];
    global.alert = (message) => alerts.push(message);

    await openOutput();

    assert.deepEqual(alerts, ["Path does not exist: /outputs"]);
  });
});
