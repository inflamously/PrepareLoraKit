import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { closeModal, showModal } from "../../../prepare_lora_kit_ui/static/components/modal.js";
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

  it("dismisses on backdrop click only, not on dialog content clicks", () => {
    const dialog = document.createElement("div");
    dialog.id = "dialog";
    let dismissed = 0;
    showModal(dialog, { onBackdrop: () => dismissed++ });

    const layer = document.getElementById("modalLayer");
    dialog.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    assert.equal(dismissed, 0, "clicks inside the dialog must not dismiss");

    layer.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    assert.equal(dismissed, 1, "clicks on the layer backdrop dismiss");
  });

  it("does not leak a backdrop listener onto the next modal", () => {
    let dismissed = 0;
    // A dismissable modal closed via something other than a backdrop click
    // (e.g. a Close button) must not leave its listener on the shared layer.
    showModal(document.createElement("div"), { onBackdrop: () => dismissed++ });
    closeModal();

    // A subsequent non-dismissable modal (e.g. the pre-step config strip) must
    // survive a backdrop click instead of being torn down by the stale listener.
    const strip = document.createElement("div");
    strip.id = "strip";
    showModal(strip);
    const layer = document.getElementById("modalLayer");
    layer.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));

    assert.equal(dismissed, 0, "stale listener must not fire");
    assert.equal(layer.classList.contains("hidden"), false);
    assert.equal(layer.firstElementChild?.id, "strip");
  });

  it("replaces the backdrop listener when one dismissable modal supersedes another", () => {
    let first = 0;
    let second = 0;
    showModal(document.createElement("div"), { onBackdrop: () => first++ });
    showModal(document.createElement("div"), { onBackdrop: () => second++ });

    const layer = document.getElementById("modalLayer");
    layer.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));

    assert.equal(first, 0, "superseded modal's listener must be detached");
    assert.equal(second, 1, "only the current modal's listener fires");
  });
});
