import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { showVaeReview } from "../../../prepare_lora_kit/ui/static/steps/vae_review/vae_review.js";
import {
  calls,
  nextTick,
  setupInteractionDom,
  vaeReviewPending,
} from "./interaction_helpers.js";

let apiCalls;

beforeEach(() => {
  ({ apiCalls } = setupInteractionDom());
});

describe("vae review interaction", () => {
  it("renders four-view cards, switches detail views, and submits input decisions", async () => {
    const onSubmitted = calls();
    showVaeReview(vaeReviewPending(), { onSubmitted });

    const layer = document.getElementById("modalLayer");
    const cards = [...layer.querySelectorAll(".vae-review-card")];
    assert.equal(layer.classList.contains("hidden"), false);
    assert.equal(cards.length, 2);
    assert.equal(cards[0].querySelectorAll(".vae-thumb").length, 4);
    assert.deepEqual(
      [...cards[0].querySelectorAll(".vae-thumb figcaption")].map((caption) =>
        caption.textContent.trim(),
      ),
      ["Original", "VAE", "Diff", "Hard Mask"],
    );
    assert.equal(cards[0].classList.contains("keep"), true);
    assert.equal(cards[1].classList.contains("replace"), true);
    assert.equal(cards[0].classList.contains("selected"), true);

    layer
      .querySelector('.vae-view-tabs [data-view="hard"]')
      .dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    assert.equal(
      layer.querySelector(".vae-detail-preview img").getAttribute("src"),
      "http://example.invalid/first-hard.png?w=2048",
    );

    layer
      .querySelector('.vae-detail-actions [data-decision="drop"]')
      .dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    assert.equal(cards[0].classList.contains("drop"), true);

    cards[1].dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    assert.equal(cards[1].classList.contains("selected"), true);
    assert.match(layer.querySelector(".vae-review-detail").textContent, /second\.png/);

    cards[1].dispatchEvent(
      new window.MouseEvent("contextmenu", { bubbles: true, cancelable: true }),
    );
    assert.equal(cards[1].classList.contains("keep"), true);
    assertPressed(layer.querySelector(".vae-detail-actions"), "keep");

    layer
      .querySelector('.vae-detail-actions [data-decision="drop"]')
      .dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    assert.equal(cards[1].classList.contains("drop"), true);

    layer.querySelector("#finishVaeReview").click();
    await nextTick();

    assert.deepEqual(apiCalls.submitted, [
      {
        jobId: "job-1",
        requestId: "vae-review-1",
        value: {
          decisions: {
            "/images/first.png": "drop",
            "/images/second.png": "drop",
          },
        },
      },
    ]);
    assert.equal(onSubmitted.count, 1);
    assert.equal(layer.classList.contains("hidden"), true);
  });

  it("renders empty state and submits empty decisions", async () => {
    const onSubmitted = calls();
    showVaeReview(
      { id: "vae-empty", kind: "vae_review", payload: { items: [] } },
      { onSubmitted },
    );

    const layer = document.getElementById("modalLayer");
    assert.match(layer.textContent, /No images to review/);
    assert.equal(layer.querySelectorAll(".vae-review-card").length, 0);

    layer.querySelector("#finishVaeReview").click();
    await nextTick();

    assert.deepEqual(apiCalls.submitted[0], {
      jobId: "job-1",
      requestId: "vae-empty",
      value: { decisions: {} },
    });
  });

  it("escapes VAE review image metadata", () => {
    showVaeReview(
      {
        id: "vae-escaped",
        kind: "vae_review",
        payload: {
          items: [
            {
              path: "/images/escaped.png",
              name: "<img onerror=alert(1)>",
              width: 32,
              height: 32,
              hf_loss: 1,
              threshold: 2,
              flagged: true,
              initial_decision: "replace",
              views: {
                original: {
                  path: "/images/escaped.png",
                  name: "escaped.png",
                  uri: "http://example.invalid/escaped.png",
                },
              },
            },
          ],
        },
      },
      { onSubmitted: async () => {} },
    );

    const layer = document.getElementById("modalLayer");
    const injected = [...layer.querySelectorAll("img")].filter(
      (img) => img.getAttribute("onerror") !== null,
    );
    assert.equal(injected.length, 0);
    assert.match(layer.textContent, /<img onerror=alert\(1\)>/);
  });
});

function assertPressed(container, decision) {
  container.querySelectorAll("[data-decision]").forEach((button) => {
    assert.equal(
      button.getAttribute("aria-pressed"),
      String(button.dataset.decision === decision),
    );
  });
}
