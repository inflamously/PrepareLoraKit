import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import {
  calls,
  captionVerifyPending,
  nextTick,
  setupInteractionDom,
} from "./interaction_helpers.js";

let apiCalls;
let showCaptionVerify;

const layer = () => document.getElementById("modalLayer");
const tiles = () => [...layer().querySelectorAll(".caption-verify-tile")];
const editor = () => layer().querySelector("textarea[data-caption]");
const verdictButtons = () => [
  ...layer().querySelectorAll(".caption-verify-verdict"),
];
const verdictButton = (value) =>
  layer().querySelector(`.caption-verify-verdict[data-decision="${value}"]`);
const activeVerdict = () =>
  verdictButtons().find((button) => button.getAttribute("aria-pressed") === "true")
    ?.dataset.decision;
const stale = () => layer().querySelector(".caption-verify-stale");
const click = (el) =>
  el.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
const press = (key, options = {}) =>
  document.dispatchEvent(
    new window.KeyboardEvent("keydown", { key, bubbles: true, ...options }),
  );

function type(textarea, value) {
  textarea.value = value;
  textarea.dispatchEvent(new window.Event("input", { bubbles: true }));
}

async function generate({ reroll = false } = {}) {
  const id = reroll ? "#rerollCaptionPreview" : "#generateCaptionPreview";
  click(layer().querySelector(id));
  await nextTick();
}

describe("caption verify modal", () => {
  beforeEach(async () => {
    ({ apiCalls } = setupInteractionDom());
    ({ showCaptionVerify } = await import(
      "../../../prepare_lora_kit_ui/static/steps/caption_verify/caption_verify.js"
    ));
  });

  it("renders one filmstrip tile per item and one caption editor", () => {
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    assert.equal(tiles().length, 2);
    assert.equal(layer().querySelectorAll("textarea[data-caption]").length, 1);
    assert.equal(editor().value, "plk_mock, a red cube.");
    assert.equal(
      layer().querySelector("#captionVerifyName").textContent,
      "first.png",
    );
    assert.deepEqual(
      verdictButtons().map((button) => button.dataset.decision),
      ["correct", "generic", "wrong"],
    );
    assert.ok(tiles()[0].classList.contains("selected"));
    assert.equal(activeVerdict(), "correct");
  });

  it("swaps the editor to the tile that was clicked", () => {
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    click(tiles()[1]);

    assert.equal(editor().value, "plk_mock, a blue sphere.");
    assert.equal(
      layer().querySelector("#captionVerifyName").textContent,
      "second.png",
    );
    assert.ok(tiles()[1].classList.contains("selected"));
    assert.ok(!tiles()[0].classList.contains("selected"));
  });

  it("steps through the strip with the nav buttons and arrow keys", () => {
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    click(layer().querySelector("#captionVerifyNext"));
    assert.ok(tiles()[1].classList.contains("selected"));

    // Clamped at both ends rather than wrapping around.
    click(layer().querySelector("#captionVerifyNext"));
    assert.ok(tiles()[1].classList.contains("selected"));

    press("ArrowLeft");
    assert.ok(tiles()[0].classList.contains("selected"));
    press("ArrowRight");
    assert.ok(tiles()[1].classList.contains("selected"));
  });

  it("judges the selected image with the 1/2/3 keys", () => {
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    press("2");

    assert.equal(activeVerdict(), "generic");
    assert.ok(tiles()[0].classList.contains("generic"));
    assert.match(
      layer().querySelector("#captionVerifyProgress").textContent,
      /1 reviewed/,
    );
  });

  it("leaves digits typed into the caption box alone", () => {
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    editor().dispatchEvent(
      new window.KeyboardEvent("keydown", { key: "3", bubbles: true }),
    );

    assert.equal(activeVerdict(), "correct");
    assert.match(
      layer().querySelector("#captionVerifyProgress").textContent,
      /0 reviewed/,
    );
  });

  it("generates on ctrl+enter, including from the caption box", async () => {
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    editor().dispatchEvent(
      new window.KeyboardEvent("keydown", {
        key: "Enter",
        ctrlKey: true,
        bubbles: true,
      }),
    );
    await nextTick();

    assert.equal(apiCalls.generated.length, 1);
    assert.equal(apiCalls.generated[0].imagePath, "/images/first.png");
  });

  it("sends the edited caption, not the original", async () => {
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    type(editor(), "a plain grey cylinder");
    await generate();

    assert.equal(apiCalls.generated.length, 1);
    assert.equal(apiCalls.generated[0].caption, "a plain grey cylinder");
    assert.equal(apiCalls.generated[0].imagePath, "/images/first.png");
    const img = layer().querySelector(".caption-verify-generated img");
    assert.match(img.getAttribute("src"), /gen_1\.png/);
  });

  it("flags a re-roll and swaps in the new render", async () => {
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    await generate();
    await generate({ reroll: true });

    assert.equal(apiCalls.generated.length, 2);
    assert.equal(apiCalls.generated[0].options.reroll, false);
    assert.equal(apiCalls.generated[1].options.reroll, true);
    const img = layer().querySelector(".caption-verify-generated img");
    assert.match(img.getAttribute("src"), /gen_2\.png/);
  });

  it("blocks a second render while one is in flight", async () => {
    let release;
    apiCalls.generateHandler = () =>
      new Promise((resolve) => {
        release = resolve;
      });
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    await generate();
    assert.equal(apiCalls.generated.length, 1);
    assert.ok(layer().querySelector("#generateCaptionPreview").disabled);

    await generate();
    assert.equal(apiCalls.generated.length, 1, "second click must not queue a job");

    release({ uri: "http://example.invalid/done.png", seed: 9, caption: "x" });
    await nextTick();
    assert.ok(!layer().querySelector("#generateCaptionPreview").disabled);
  });

  it("routes a late render to the image it was started for", async () => {
    let release;
    apiCalls.generateHandler = (call) =>
      new Promise((resolve) => {
        release = () =>
          resolve({
            uri: `http://example.invalid/for_first.png`,
            view_uri: `http://example.invalid/for_first.png?w=2048`,
            seed: 5,
            caption: call.caption,
          });
      });
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    await generate();
    click(tiles()[1]); // move on while the first render is still running
    release();
    await nextTick();

    // The second image must not be showing the first image's render.
    assert.equal(layer().querySelector(".caption-verify-generated img"), null);

    click(tiles()[0]);
    await nextTick();
    assert.match(
      layer().querySelector(".caption-verify-generated img").getAttribute("src"),
      /for_first\.png/,
    );
  });

  it("cycles the verdict on a right-click on a tile", () => {
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    tiles()[0].dispatchEvent(
      new window.MouseEvent("contextmenu", { bubbles: true, cancelable: true }),
    );

    assert.ok(tiles()[0].classList.contains("generic"));
    assert.equal(activeVerdict(), "generic", "the editor follows the tile");
  });

  it("keeps caption edits across re-selection", async () => {
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    type(editor(), "edited text");
    click(tiles()[1]);
    assert.equal(editor().value, "plk_mock, a blue sphere.");
    click(tiles()[0]);

    assert.equal(editor().value, "edited text");
    assert.ok(tiles()[0].classList.contains("caption-verify-tile--edited"));
    click(layer().querySelector("#finishCaptionVerify"));
    await nextTick();
    assert.equal(
      apiCalls.submitted[0].value.items["/images/first.png"].caption,
      "edited text",
    );
  });

  it("marks a render stale once the caption changes underneath it", async () => {
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    await generate();
    assert.ok(stale().hidden);

    type(editor(), "different caption");
    assert.ok(!stale().hidden);

    await generate();
    assert.ok(stale().hidden);
  });

  it("counts characters always and tokens only for the render on screen", async () => {
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });
    const count = () => layer().querySelector("#captionVerifyCount").textContent;

    assert.equal(count(), "21 chars");

    await generate();
    assert.equal(count(), "5 tokens · 21 chars");

    // The counted tokens belong to the caption that was rendered, not this one.
    type(editor(), "a red cube");
    assert.equal(count(), "10 chars");
  });

  it("submits verdicts and captions per path", async () => {
    const onSubmitted = calls();
    showCaptionVerify(captionVerifyPending(), { onSubmitted });

    click(verdictButton("wrong"));
    type(editor(), "a red cube");
    click(layer().querySelector("#finishCaptionVerify"));
    await nextTick();

    assert.deepEqual(apiCalls.submitted, [
      {
        jobId: "job-1",
        requestId: "caption-verify-1",
        value: {
          items: {
            "/images/first.png": {
              verdict: "wrong",
              caption: "a red cube",
              edited: true,
            },
            "/images/second.png": {
              verdict: "correct",
              caption: "plk_mock, a blue sphere.",
              edited: false,
            },
          },
        },
      },
    ]);
    assert.equal(onSubmitted.count, 1);
  });

  it("shows an empty state and submits nothing for an empty payload", async () => {
    showCaptionVerify(captionVerifyPending("caption-verify-2", []), {
      onSubmitted: calls(),
    });

    assert.equal(tiles().length, 0);
    assert.match(layer().textContent, /No captions to verify/);
    assert.ok(editor().disabled);
    assert.ok(verdictButtons().every((button) => button.disabled));

    click(layer().querySelector("#finishCaptionVerify"));
    await nextTick();
    assert.deepEqual(apiCalls.submitted[0].value, { items: {} });
  });

  it("escapes hostile names and captions", () => {
    const hostile = {
      path: "/images/x.png",
      name: "<img onerror=alert(1) src=x>",
      uri: "http://example.invalid/x.png",
      thumb_uri: "http://example.invalid/x.png?w=384",
      view_uri: "http://example.invalid/x.png?w=2048",
      width: 8,
      height: 8,
      caption: "</textarea><img onerror=alert(1) src=x>",
      caption_path: "/images/x.txt",
      has_caption: true,
      initial_verdict: "correct",
    };

    showCaptionVerify(captionVerifyPending("caption-verify-3", [hostile]), {
      onSubmitted: calls(),
    });

    const injected = [...layer().querySelectorAll("img")].filter((img) =>
      img.hasAttribute("onerror"),
    );
    assert.equal(injected.length, 0);
    assert.equal(
      editor().value,
      "</textarea><img onerror=alert(1) src=x>",
      "the caption survives verbatim as a value, never as markup",
    );
    assert.match(layer().textContent, /<img onerror=alert\(1\) src=x>/);
  });

  it("surfaces a render error and re-enables the button", async () => {
    apiCalls.generateHandler = () => {
      throw new Error("CUDA out of memory");
    };
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    await generate();

    assert.match(
      layer().querySelector(".caption-verify-error").textContent,
      /CUDA out of memory/,
    );
    assert.ok(!layer().querySelector("#generateCaptionPreview").disabled);
  });

  it("warns when the encoder truncated the caption", async () => {
    apiCalls.generateHandler = (call) => ({
      uri: "http://example.invalid/t.png",
      seed: 1,
      caption: call.caption,
      truncated: true,
      token_count: 90,
    });
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    await generate();

    assert.match(
      layer().querySelector(".caption-verify-truncated").textContent,
      /90 tokens/,
    );
  });

  it("counts reviewed images in the header and dots only judged tiles", () => {
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    assert.match(layer().querySelector("#captionVerifyProgress").textContent, /0 reviewed/);
    assert.ok(
      tiles().every(
        (tile) => !tile.classList.contains("caption-verify-tile--reviewed"),
      ),
      "an unjudged tile must not wear the default verdict's colour",
    );

    click(verdictButton("generic"));

    assert.match(layer().querySelector("#captionVerifyProgress").textContent, /1 reviewed/);
    assert.ok(tiles()[0].classList.contains("caption-verify-tile--reviewed"));
    assert.ok(!tiles()[1].classList.contains("caption-verify-tile--reviewed"));
  });

  it("auto-renders on select only once per image", async () => {
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    // Opening the modal must not render anything on its own.
    assert.equal(apiCalls.generated.length, 0);

    click(tiles()[1]);
    await nextTick();
    assert.equal(apiCalls.generated.length, 1);
    assert.equal(apiCalls.generated[0].imagePath, "/images/second.png");

    click(tiles()[0]);
    await nextTick();
    click(tiles()[1]);
    await nextTick();

    const forSecond = apiCalls.generated.filter(
      (call) => call.imagePath === "/images/second.png",
    );
    assert.equal(forSecond.length, 1, "a cached render must not re-fire");
  });

  it("does not auto-render when the toggle is off", async () => {
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    layer().querySelector("#captionVerifyAuto").checked = false;
    click(tiles()[1]);
    await nextTick();

    assert.equal(apiCalls.generated.length, 0);
  });

  it("renders live model status from the job poll", async () => {
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    const { state } = await import(
      "../../../prepare_lora_kit_ui/static/core/state.js"
    );
    state.job = {
      caption_status: { phase: "generating", message: "Denoising 3/4" },
    };
    global.dispatchEvent(
      new window.CustomEvent("plk:job-status", { detail: state.job }),
    );

    assert.match(layer().querySelector("#captionVerifyStatus").textContent, /Denoising 3\/4/);
  });

  it("stops listening for job status and keys after submitting", async () => {
    showCaptionVerify(captionVerifyPending(), { onSubmitted: calls() });

    click(layer().querySelector("#finishCaptionVerify"));
    await nextTick();

    // Must not throw against the torn-down modal.
    global.dispatchEvent(
      new window.CustomEvent("plk:job-status", {
        detail: { caption_status: { phase: "idle", message: "x" } },
      }),
    );
    press("2");
    press("ArrowRight");
    assert.equal(layer().querySelector(".caption-verify-modal"), null);
  });

  it("disables rendering for an image with no caption", () => {
    const item = {
      path: "/images/blank.png",
      name: "blank.png",
      uri: "http://example.invalid/blank.png",
      thumb_uri: "http://example.invalid/blank.png?w=384",
      view_uri: "http://example.invalid/blank.png?w=2048",
      width: 8,
      height: 8,
      caption: "",
      caption_path: "/images/blank.txt",
      has_caption: false,
      initial_verdict: "correct",
    };

    showCaptionVerify(captionVerifyPending("caption-verify-4", [item]), {
      onSubmitted: calls(),
    });

    assert.ok(layer().querySelector("#generateCaptionPreview").disabled);
    assert.ok(tiles()[0].classList.contains("caption-verify-tile--nocaption"));
  });
});
