import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { bootOnPywebviewReady } from "../../../prepare_lora_kit_ui/static/core/boot.js";

describe("bootOnPywebviewReady", () => {
  it("boots immediately when the readiness event already fired", () => {
    const target = new EventTarget();
    target.pywebview = { api: {} };
    let calls = 0;

    bootOnPywebviewReady(() => { calls += 1; }, target);
    target.dispatchEvent(new Event("pywebviewready"));

    assert.equal(calls, 1);
  });

  it("waits for pywebview and boots only once", () => {
    const target = new EventTarget();
    let calls = 0;

    bootOnPywebviewReady(() => { calls += 1; }, target);
    target.pywebview = { api: {} };
    target.dispatchEvent(new Event("pywebviewready"));
    target.dispatchEvent(new Event("pywebviewready"));

    assert.equal(calls, 1);
  });
});
