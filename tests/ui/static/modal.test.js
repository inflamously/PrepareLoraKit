import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { closeModal, showModal } from "../../../prepare_lora_kit/ui/static/interaction/modal.js";
import { setupInteractionDom } from "./interaction_helpers.js";

beforeEach(() => {
  setupInteractionDom();
});

describe("modal helpers", () => {
  it("shows, replaces, and closes modal content", () => {
    const first = document.createElement("section");
    first.id = "first";
    const second = document.createElement("section");
    second.id = "second";

    showModal(first);

    const layer = document.getElementById("modalLayer");
    assert.equal(layer.classList.contains("hidden"), false);
    assert.equal(layer.firstElementChild.id, "first");

    showModal(second);
    assert.equal(layer.children.length, 1);
    assert.equal(layer.firstElementChild.id, "second");

    closeModal();
    assert.equal(layer.classList.contains("hidden"), true);
    assert.equal(layer.children.length, 0);
  });
});
