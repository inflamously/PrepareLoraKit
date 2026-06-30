import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { showUpscaleReview } from "../../../prepare_lora_kit/ui/static/steps/upscale_review/upscale_review.js";
import {
  calls,
  nextTick,
  setupInteractionDom,
  upscaleReviewPending,
} from "./interaction_helpers.js";

let apiCalls;

beforeEach(() => {
  ({ apiCalls } = setupInteractionDom());
});

describe("upscale review interaction", () => {
  it("renders cards, switches selection, and submits input decisions", async () => {
    const onSubmitted = calls();
    showUpscaleReview(upscaleReviewPending(), { onSubmitted });

    const layer = document.getElementById("modalLayer");
    const cards = [...layer.querySelectorAll(".upscale-review-card")];
    assert.equal(layer.classList.contains("hidden"), false);
    assert.equal(cards.length, 2);
    assert.equal(cards[0].classList.contains("upscale"), true);
    assert.equal(cards[0].classList.contains("selected"), true);
    assert.match(layer.querySelector(".upscale-review-detail").textContent, /first\.jpg/);
    assert.match(layer.querySelector(".upscale-review-detail").textContent, /Upscale/);

    cards[1].dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    assert.equal(cards[1].classList.contains("selected"), true);
    assert.match(layer.querySelector(".upscale-review-detail").textContent, /second\.jpg/);
    assert.match(
      layer.querySelector(".upscale-review-detail").textContent,
      /JPEG cleanup \(downscale then re-upscale\)/,
    );

    layer
      .querySelector('.upscale-detail-actions [data-decision="skip"]')
      .dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    assert.equal(cards[1].classList.contains("skip"), true);

    cards[1].dispatchEvent(
      new window.MouseEvent("contextmenu", { bubbles: true, cancelable: true }),
    );
    assert.equal(cards[1].classList.contains("upscale"), true);

    layer
      .querySelector('.upscale-detail-actions [data-decision="skip"]')
      .dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    assert.equal(cards[1].classList.contains("skip"), true);

    layer.querySelector("#finishUpscaleReview").click();
    await nextTick();

    assert.deepEqual(apiCalls.submitted, [
      {
        jobId: "job-1",
        requestId: "upscale-review-1",
        value: {
          decisions: {
            "/images/first.jpg": "upscale",
            "/images/second.jpg": "skip",
          },
        },
      },
    ]);
    assert.equal(onSubmitted.count, 1);
    assert.equal(layer.classList.contains("hidden"), true);
  });

  it("renders empty state and submits empty decisions", async () => {
    const onSubmitted = calls();
    showUpscaleReview(
      { id: "upscale-empty", kind: "upscale_review", payload: { items: [] } },
      { onSubmitted },
    );

    const layer = document.getElementById("modalLayer");
    assert.match(layer.textContent, /Nothing was flagged for review/);
    assert.equal(layer.querySelectorAll(".upscale-review-card").length, 0);

    layer.querySelector("#finishUpscaleReview").click();
    await nextTick();

    assert.deepEqual(apiCalls.submitted[0], {
      jobId: "job-1",
      requestId: "upscale-empty",
      value: { decisions: {} },
    });
  });

  it("escapes upscale review image metadata", () => {
    showUpscaleReview(
      {
        id: "upscale-escaped",
        kind: "upscale_review",
        payload: {
          items: [
            {
              path: "/images/escaped.jpg",
              name: "<img onerror=alert(1)>",
              uri: "http://example.invalid/escaped.jpg",
              width: 32,
              height: 32,
              min_side: 32,
              threshold: 1536,
              is_jpeg: true,
              planned_action: "upscale",
              flagged: true,
              initial_decision: "upscale",
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
