import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  buildSubmitValue,
  createImageStates,
  effectiveSkipped,
  firstUncaptionedIndex,
  imageStripState,
} from "../../../prepare_lora_kit_ui/static/steps/bbox_annotation/batch.js";

function statesFixture() {
  return createImageStates({
    images: [
      { path: "/a.png", name: "a.png", uri: "u/a", annotations: [], done: false },
      {
        path: "/b.png",
        name: "b.png",
        uri: "u/b",
        annotations: [{ x1: 0, y1: 0, x2: 1, y2: 1, label: "a cat" }],
        done: true,
      },
    ],
  });
}

describe("createImageStates", () => {
  it("builds per-image state with pre-filled boxes and flags", () => {
    const states = statesFixture();
    assert.equal(states.length, 2);
    assert.deepEqual(states[0].boxes, []);
    assert.equal(states[0].done, false);
    assert.equal(states[1].done, true);
    assert.equal(states[1].boxes[0].label, "a cat");
    // Boxes are copied, not shared with the payload.
    assert.notEqual(states[1].boxes[0], undefined);
  });

  it("tolerates a missing/empty payload", () => {
    assert.deepEqual(createImageStates(undefined), []);
    assert.deepEqual(createImageStates({ images: null }), []);
  });

  it("carries downscaled thumb/view variants, falling back to uri", () => {
    const [withVariants, plain] = createImageStates({
      images: [
        {
          path: "/a.png",
          name: "a.png",
          uri: "u/a",
          thumb_uri: "u/a&w=384",
          view_uri: "u/a&w=2048",
          annotations: [],
        },
        { path: "/b.png", name: "b.png", uri: "u/b", annotations: [] },
      ],
    });
    assert.equal(withVariants.thumbUri, "u/a&w=384");
    assert.equal(withVariants.viewUri, "u/a&w=2048");
    // No variants provided → both fall back to the full uri.
    assert.equal(plain.thumbUri, "u/b");
    assert.equal(plain.viewUri, "u/b");
  });
});

describe("effectiveSkipped", () => {
  it("keeps untouched done images, captions edited or new images", () => {
    const [fresh, done] = statesFixture();
    assert.equal(effectiveSkipped(fresh), false); // new image → caption
    assert.equal(effectiveSkipped(done), true); // untouched done → keep
    done.dirty = true;
    assert.equal(effectiveSkipped(done), false); // edited done → recaption
    done.dirty = false;
    done.skipped = true;
    assert.equal(effectiveSkipped(done), true); // explicit skip wins
  });
});

describe("buildSubmitValue", () => {
  it("Done captions new images and keeps untouched done images", () => {
    const states = statesFixture();
    states[0].boxes.push({ x1: 0, y1: 0, x2: 0.5, y2: 0.5, label: "a dog" });
    const value = buildSubmitValue(states, { skipAll: false });

    assert.equal(value.skip_all, false);
    assert.deepEqual(value.images["/a.png"], {
      annotations: [{ x1: 0, y1: 0, x2: 0.5, y2: 0.5, label: "a dog" }],
      skipped: false,
    });
    // Untouched done image is kept (skipped), though its boxes still travel.
    assert.equal(value.images["/b.png"].skipped, true);
    assert.equal(value.images["/b.png"].annotations[0].label, "a cat");
  });

  it("drops boxes whose label is blank", () => {
    const states = statesFixture();
    states[0].boxes.push({ x1: 0, y1: 0, x2: 1, y2: 1, label: "  " });
    const value = buildSubmitValue(states, { skipAll: false });
    assert.deepEqual(value.images["/a.png"].annotations, []);
  });

  it("skip-all captions the active image and skips other untouched images", () => {
    const states = statesFixture();
    states[1].done = false; // make b a fresh, un-captioned image
    const value = buildSubmitValue(states, { skipAll: true, activeIndex: 0 });

    assert.equal(value.skip_all, true);
    assert.equal(value.images["/a.png"].skipped, false); // active applied
    assert.equal(value.images["/b.png"].skipped, true); // remaining skipped
  });

  it("skip-all still honors edits already made this session", () => {
    const states = statesFixture();
    states[1].done = false;
    states[1].dirty = true; // user edited b earlier
    const value = buildSubmitValue(states, { skipAll: true, activeIndex: 0 });
    assert.equal(value.images["/b.png"].skipped, false);
  });
});

describe("firstUncaptionedIndex", () => {
  it("flags an un-captioned box on an image that will be captioned", () => {
    const states = statesFixture();
    states[0].boxes.push({ x1: 0, y1: 0, x2: 1, y2: 1, label: "region 1" });
    assert.equal(firstUncaptionedIndex(states), 0);
  });

  it("ignores un-captioned boxes on skipped images", () => {
    const states = statesFixture();
    // b is an untouched done image → skipped → its placeholder box must not block.
    states[1].boxes.push({ x1: 0, y1: 0, x2: 1, y2: 1, label: "region 2" });
    assert.equal(firstUncaptionedIndex(states), -1);
  });
});

describe("imageStripState", () => {
  it("classifies each thumbnail", () => {
    const [fresh, done] = statesFixture();
    assert.equal(imageStripState(done), "done");
    assert.equal(imageStripState(fresh), "empty");
    fresh.boxes.push({ x1: 0, y1: 0, x2: 1, y2: 1, label: "x" });
    assert.equal(imageStripState(fresh), "has-boxes");
    fresh.skipped = true;
    assert.equal(imageStripState(fresh), "skipped");
  });
});
