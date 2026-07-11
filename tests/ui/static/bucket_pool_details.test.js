import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import {
  cropLossPercentage,
  showBucketPoolDetails,
} from "../../../prepare_lora_kit_ui/static/steps/bucket_pool_details/bucket_pool_details.js";
import { calls, nextTick, setupInteractionDom } from "./interaction_helpers.js";

let apiCalls;

beforeEach(() => {
  ({ apiCalls } = setupInteractionDom());
});

describe("bucket pool details interaction", () => {
  it("shows every configured bucket and selects a thin populated bucket first", () => {
    showBucketPoolDetails(bucketPending(), { onSubmitted: async () => {} });

    const layer = document.getElementById("modalLayer");
    const cards = [...layer.querySelectorAll(".bucket-pool-card")];
    assert.equal(cards.length, 3);
    assert.match(cards[0].textContent, /1024×1024/);
    assert.equal(cards[1].disabled, true);
    assert.equal(cards[1].classList.contains("empty"), true);
    assert.match(layer.querySelector(".bucket-pool-card.selected").textContent, /768×1344/);
    assert.match(layer.querySelector(".bucket-detail-title strong").textContent, /portrait\.png/);

    const crop = layer.querySelector(".bucket-crop-shape");
    assert.equal(crop.style.width, "171px");
    assert.equal(crop.style.height, "300px");
    assert.match(layer.textContent, /Small pools repeat the same examples/);
  });

  it("updates assigned images and the preview when selections change", () => {
    showBucketPoolDetails(bucketPending(), { onSubmitted: async () => {} });
    const layer = document.getElementById("modalLayer");

    layer.querySelectorAll(".bucket-pool-card")[0].click();
    let imageCards = layer.querySelectorAll(".bucket-image-card");
    assert.equal(imageCards.length, 2);
    assert.match(layer.querySelector(".bucket-detail-title strong").textContent, /wide\.png/);

    imageCards[1].click();
    assert.match(layer.querySelector(".bucket-detail-title strong").textContent, /square\.png/);
    assert.match(layer.querySelector(".bucket-detail-metrics").textContent, /1024×1024/);
  });

  it("confirms and resumes the pipeline", async () => {
    const onSubmitted = calls();
    showBucketPoolDetails(bucketPending(), { onSubmitted });

    document.getElementById("continueBucketPoolDetails").click();
    await nextTick();

    assert.deepEqual(apiCalls.submitted, [{
      jobId: "job-1",
      requestId: "bucket-details-1",
      value: { confirmed: true },
    }]);
    assert.equal(onSubmitted.count, 1);
    assert.equal(document.getElementById("modalLayer").classList.contains("hidden"), true);
  });

  it("escapes report, image, and suggestion metadata", () => {
    const pending = bucketPending();
    pending.payload.report_path = "<img src=x onerror=alert(1)>";
    pending.payload.buckets[2].images[0].name = "<script>bad</script>";
    pending.payload.buckets[2].suggestion = "<img src=x>";

    showBucketPoolDetails(pending, { onSubmitted: async () => {} });

    const layer = document.getElementById("modalLayer");
    assert.equal(layer.querySelectorAll("script").length, 0);
    assert.equal(layer.querySelectorAll(".bucket-suggestion img").length, 0);
    assert.match(layer.textContent, /<script>bad<\/script>/);
  });
});

describe("bucket crop estimate", () => {
  it("reports edge loss from aspect-ratio crop", () => {
    assert.equal(cropLossPercentage({ width: 1600, height: 900 }, { width: 1024, height: 1024 }), 44);
    assert.equal(cropLossPercentage({ width: 1024, height: 1024 }, { width: 512, height: 512 }), 0);
    assert.equal(cropLossPercentage({ width: null, height: null }, { width: 512, height: 512 }), null);
  });
});

function image(name, width, height) {
  const uri = `http://example.invalid/${name}`;
  return {
    path: `/images/${name}`,
    name,
    width,
    height,
    uri,
    thumb_uri: `${uri}?w=384`,
    view_uri: `${uri}?w=2048`,
  };
}

function bucketPending() {
  return {
    id: "bucket-details-1",
    kind: "bucket_pool_details",
    payload: {
      report_path: "/reports/BucketPoolsCheckStep_report.json",
      thin_threshold: 2,
      summary: { total_images: 3, populated_buckets: 2, thin_buckets: 1 },
      buckets: [
        {
          width: 1024,
          height: 1024,
          count: 2,
          status: "healthy",
          suggestion: "",
          images: [image("wide.png", 1600, 900), image("square.png", 1024, 1024)],
        },
        {
          width: 1536,
          height: 640,
          count: 0,
          status: "empty",
          suggestion: "",
          images: [],
        },
        {
          width: 768,
          height: 1344,
          count: 1,
          status: "thin",
          suggestion: "centre-crop width",
          images: [image("portrait.png", 900, 1600)],
        },
      ],
    },
  };
}
