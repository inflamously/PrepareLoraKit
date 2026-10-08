import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { showUpscaleReview } from "../../../prepare_lora_kit_ui/static/steps/upscale_review/upscale_review.js";
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
    const cardFor = (name) =>
      [...layer.querySelectorAll(".upscale-review-card")].find((card) =>
        card.textContent.includes(name),
      );
    const detailText = () => layer.querySelector(".upscale-review-detail").textContent;
    assert.equal(layer.classList.contains("hidden"), false);
    assert.equal(layer.querySelectorAll(".upscale-review-card").length, 3);
    assert.equal(cardFor("first.jpg").classList.contains("upscale"), true);
    assert.equal(cardFor("first.jpg").classList.contains("selected"), true);
    assert.match(detailText(), /first\.jpg/);
    assert.match(detailText(), /Upscale/);

    const second = cardFor("second.jpg");
    second.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    assert.equal(second.classList.contains("selected"), true);
    assert.equal(second.classList.contains("cleanup"), true);
    assert.match(detailText(), /second\.jpg/);
    assert.match(detailText(), /JPEG cleanup → PNG, same size/);
    assert.match(detailText(), /2816–3071px/);

    layer
      .querySelector('.upscale-detail-actions [data-decision="skip"]')
      .dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    assert.equal(second.classList.contains("skip"), true);

    second.dispatchEvent(
      new window.MouseEvent("contextmenu", { bubbles: true, cancelable: true }),
    );
    assert.equal(second.classList.contains("upscale"), true);

    layer
      .querySelector('.upscale-detail-actions [data-decision="skip"]')
      .dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    assert.equal(second.classList.contains("skip"), true);

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
            "/images/third.png": "upscale",
          },
        },
      },
    ]);
    assert.equal(onSubmitted.count, 1);
    assert.equal(layer.classList.contains("hidden"), true);
  });

  it("groups cards into min-side tiers, smallest first", () => {
    showUpscaleReview(upscaleReviewPending(), { onSubmitted: async () => {} });

    const layer = document.getElementById("modalLayer");
    const tiers = [...layer.querySelectorAll(".upscale-tier")];
    assert.deepEqual(tiers.map((tier) => tier.dataset.tier), ["1024", "2816"]);
    assert.match(tiers[0].querySelector(".upscale-tier-header").textContent, /1024–1279px/);
    assert.match(tiers[0].querySelector(".upscale-tier-header").textContent, /2 images/);
    assert.equal(tiers[0].querySelectorAll(".upscale-review-card").length, 2);
    assert.equal(tiers[1].querySelectorAll(".upscale-review-card").length, 1);
    assert.match(layer.textContent, /3 candidates in 2 min-side tiers/);

    tiers[0].querySelector(".upscale-tier-toggle").click();
    assert.equal(tiers[0].querySelector(".upscale-tier-grid").hidden, true);
  });

  it("keep size cleans up JPEGs and skips the rest; upscale all reverts", async () => {
    showUpscaleReview(upscaleReviewPending(), { onSubmitted: async () => {} });

    const layer = document.getElementById("modalLayer");
    const tier = layer.querySelector('.upscale-tier[data-tier="1024"]');
    tier.querySelector('[data-tier-action="keep"]').click();
    const cards = [...tier.querySelectorAll(".upscale-review-card")];
    assert.equal(cards[0].classList.contains("cleanup"), true);
    assert.equal(cards[1].classList.contains("skip"), true);
    assert.match(layer.querySelector(".upscale-review-detail").textContent, /same size/);

    // A per-card override inside a bulk-decided tier still sticks.
    cards[1].dispatchEvent(
      new window.MouseEvent("contextmenu", { bubbles: true, cancelable: true }),
    );
    assert.equal(cards[1].classList.contains("upscale"), true);

    layer.querySelector('.upscale-tier[data-tier="2816"] [data-tier-action="upscale"]').click();
    layer.querySelector("#finishUpscaleReview").click();
    await nextTick();

    assert.deepEqual(apiCalls.submitted[0].value.decisions, {
      "/images/first.jpg": "cleanup",
      "/images/second.jpg": "upscale",
      "/images/third.png": "upscale",
    });
  });

  it("offers cleanup only for JPEGs and upscale only below the target", () => {
    showUpscaleReview(
      {
        id: "upscale-options",
        kind: "upscale_review",
        payload: {
          items: [
            { path: "/images/big.jpg", name: "big.jpg", min_side: 4000, target: 3072,
              tier_lo: 3840, tier_hi: 4095, is_jpeg: true, planned_action: "jpeg_cleanup",
              initial_decision: "cleanup" },
            { path: "/images/small.png", name: "small.png", min_side: 500, target: 3072,
              tier_lo: 256, tier_hi: 511, is_jpeg: false, planned_action: "upscale",
              initial_decision: "upscale" },
          ],
        },
      },
      { onSubmitted: async () => {} },
    );

    const layer = document.getElementById("modalLayer");
    const options = () =>
      [...layer.querySelectorAll(".upscale-detail-actions [data-decision]")].map(
        (button) => button.dataset.decision,
      );
    assert.deepEqual(options(), ["upscale", "skip"]);
    layer
      .querySelector('.upscale-tier[data-tier="3840"] .upscale-review-card')
      .dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    assert.deepEqual(options(), ["cleanup", "skip"]);
  });

  it("renders empty state and submits empty decisions", async () => {
    const onSubmitted = calls();
    showUpscaleReview(
      { id: "upscale-empty", kind: "upscale_review", payload: { items: [] } },
      { onSubmitted },
    );

    const layer = document.getElementById("modalLayer");
    assert.match(layer.textContent, /No image needs upscaling or cleanup/);
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
