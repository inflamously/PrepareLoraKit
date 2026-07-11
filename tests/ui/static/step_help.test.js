import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { STEP_HELP } from "../../../prepare_lora_kit_ui/static/steps/step_help/help_content.js";
import { showStepHelp } from "../../../prepare_lora_kit_ui/static/steps/step_help/step_help.js";
import { setupInteractionDom } from "./interaction_helpers.js";

beforeEach(() => {
  setupInteractionDom();
});

describe("VAE step help", () => {
  it("documents the process and review behavior in dedicated tabs", () => {
    showStepHelp("VaeGateStep");

    const layer = document.getElementById("modalLayer");
    const labels = [...layer.querySelectorAll(".step-help__tab")].map((tab) =>
      tab.textContent.trim(),
    );
    assert.deepEqual(labels, ["Overview", "Process", "Review Guide", "Substeps", "Parameters"]);
    assert.match(layer.textContent, /mean \+ outlier sigma/);
    assert.match(layer.textContent, /never used as a training replacement/);
    assert.match(layer.textContent, /matching \.txt caption/);
    assert.match(layer.textContent, /excluded from statistics/);
  });

  it("escapes help text", () => {
    const original = STEP_HELP.VaeGateStep.detail;
    STEP_HELP.VaeGateStep.detail = '<img src=x onerror="alert(1)">';
    try {
      showStepHelp("VaeGateStep");
      const layer = document.getElementById("modalLayer");
      assert.equal(layer.querySelector("img"), null);
      assert.match(layer.textContent, /<img src=x/);
    } finally {
      STEP_HELP.VaeGateStep.detail = original;
    }
  });
});
