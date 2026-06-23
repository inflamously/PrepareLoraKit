import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { showSourceReview } from "../../../prepare_lora_kit/ui/static/steps/source_review/source_review.js";
import {
  calls,
  nextTick,
  setupInteractionDom,
  sourceReviewPending,
} from "./interaction_helpers.js";

let apiCalls;

beforeEach(() => {
  ({ apiCalls } = setupInteractionDom());
});

describe("source review interaction", () => {
  it("renders review decisions, updates detail state, and submits payload", async () => {
    const onSubmitted = calls();
    showSourceReview(sourceReviewPending(), { onSubmitted });

    const layer = document.getElementById("modalLayer");
    const cards = [...layer.querySelectorAll(".review-card")];
    assert.equal(layer.classList.contains("hidden"), false);
    assert.equal(cards.length, 2);
    assert.equal(cards[0].classList.contains("keep"), true);
    assert.equal(cards[1].classList.contains("keep"), true);
    assert.equal(cards[0].classList.contains("selected"), true);
    assert.match(layer.querySelector(".source-review-detail").textContent, /first\.png/);

    cards[1].dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    assert.equal(cards[1].classList.contains("selected"), true);
    assert.equal(cards[1].classList.contains("keep"), true);
    assert.match(layer.querySelector(".source-review-detail").textContent, /second\.png/);
    assert.match(layer.querySelector(".source-review-detail").textContent, /needs review/);

    cards[0].dispatchEvent(
      new window.MouseEvent("contextmenu", { bubbles: true, cancelable: true }),
    );
    assert.equal(cards[0].classList.contains("reject"), true);
    assertPressed(cards[0], "reject");

    cards[0]
      .querySelector('[data-decision="flag"]')
      .dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    assert.equal(cards[0].classList.contains("flag"), true);
    assertPressed(cards[0], "flag");

    layer.querySelector("#finishReview").click();
    await nextTick();

    assert.deepEqual(apiCalls.submitted, [
      {
        jobId: "job-1",
        requestId: "review-1",
        value: {
          decisions: {
            "/images/first.png": "flag",
            "/images/second.png": "keep",
          },
        },
      },
    ]);
    assert.equal(onSubmitted.count, 1);
    assert.equal(layer.classList.contains("hidden"), true);
    assert.equal(layer.children.length, 0);
  });

  it("renders the empty review state and submits empty decisions", async () => {
    const onSubmitted = calls();
    showSourceReview(
      { id: "review-empty", kind: "source_review", payload: { items: [] } },
      { onSubmitted },
    );

    const layer = document.getElementById("modalLayer");
    assert.match(layer.textContent, /No images to review/);
    assert.equal(layer.querySelectorAll(".review-card").length, 0);

    layer.querySelector("#finishReview").click();
    await nextTick();

    assert.deepEqual(apiCalls.submitted[0], {
      jobId: "job-1",
      requestId: "review-empty",
      value: { decisions: {} },
    });
    assert.equal(onSubmitted.count, 1);
  });

  it("escapes source review image metadata", () => {
    showSourceReview(
      {
        id: "review-escaped",
        kind: "source_review",
        payload: {
          items: [
            {
              path: "/images/escaped.png",
              name: "<img onerror=alert(1)>",
              uri: "http://example.invalid/escaped.png",
              scores: { bad: "<script>" },
              quality: "bad",
              auto_reject: false,
              auto_reasons: ["<b>reason</b>"],
              initial_decision: "keep",
            },
          ],
        },
      },
      { onSubmitted: async () => {} },
    );

    const layer = document.getElementById("modalLayer");
    assert.equal(layer.querySelectorAll(".review-meta img").length, 0);
    assert.match(layer.textContent, /<img onerror=alert\(1\)>/);
    assert.match(layer.textContent, /<b>reason<\/b>/);
  });
});

function assertPressed(card, decision) {
  card.querySelectorAll("[data-decision]").forEach((button) => {
    assert.equal(
      button.getAttribute("aria-pressed"),
      String(button.dataset.decision === decision),
    );
  });
}
