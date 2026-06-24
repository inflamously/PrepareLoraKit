import { JSDOM } from "jsdom";

import { state } from "../../../prepare_lora_kit/ui/static/core/state.js";

export const nextTick = () => new Promise((resolve) => setTimeout(resolve, 0));

export function setupInteractionDom() {
  const dom = new JSDOM(
    `<!doctype html><body><div id="modalLayer" class="modal-layer hidden"></div></body>`,
    { url: "http://localhost/" },
  );
  global.window = dom.window;
  global.document = dom.window.document;
  global.Element = dom.window.Element;
  global.addEventListener = dom.window.addEventListener.bind(dom.window);
  global.removeEventListener = dom.window.removeEventListener.bind(dom.window);
  global.dispatchEvent = dom.window.dispatchEvent.bind(dom.window);
  global.CustomEvent = dom.window.CustomEvent;

  const contextCalls = [];
  dom.window.HTMLCanvasElement.prototype.getContext = () =>
    canvasContext(contextCalls);
  dom.window.HTMLCanvasElement.prototype.setPointerCapture = () => {};
  dom.window.HTMLCanvasElement.prototype.releasePointerCapture = () => {};
  dom.window.HTMLCanvasElement.prototype.hasPointerCapture = () => true;

  const apiCalls = {
    submitted: [],
    captioned: [],
  };
  window.pywebview = {
    api: {
      submit_interaction: async (jobId, requestId, value) => {
        apiCalls.submitted.push({ jobId, requestId, value });
        return { accepted: true };
      },
      caption_region: async (jobId, imagePath, box) => {
        apiCalls.captioned.push({
          jobId,
          imagePath,
          box: structuredClone(box),
        });
        return {
          caption: "captioned region",
          crop_path: "/tmp/crop.png",
          crop_name: "crop.png",
          sidecar_path: "/tmp/crop.txt",
        };
      },
    },
  };
  global.pywebview = window.pywebview;

  state.jobId = "job-1";
  state.job = { caption_status: null };
  state.handledRequestId = null;
  window.alert = () => {};
  window.prompt = () => "prompt label";
  window.innerWidth = 1280;
  window.innerHeight = 900;
  global.alert = window.alert;
  global.prompt = window.prompt;
  global.innerWidth = window.innerWidth;
  global.innerHeight = window.innerHeight;

  return { apiCalls, contextCalls };
}

export function calls() {
  const fn = async () => {
    fn.count += 1;
  };
  fn.count = 0;
  return fn;
}

export function sourceReviewPending() {
  return {
    id: "review-1",
    kind: "source_review",
    payload: {
      items: [
        {
          path: "/images/first.png",
          name: "first.png",
          uri: "http://example.invalid/first.png",
          scores: { blur: 0.12345, nested: { value: 2 } },
          quality: 91,
          auto_reject: false,
          auto_reasons: [],
          initial_decision: "keep",
        },
        {
          path: "/images/second.png",
          name: "second.png",
          uri: "http://example.invalid/second.png",
          scores: { exposure: null },
          quality: "82",
          auto_reject: true,
          auto_reasons: ["needs review"],
          initial_decision: "unknown",
        },
      ],
    },
  };
}

export function annotationPending(id = "annotation-1") {
  return {
    id,
    kind: "bbox_annotation",
    payload: {
      path: "/images/annotate.png",
      name: "annotate.png",
      uri: "http://example.invalid/annotate.png",
    },
  };
}

export function vaeReviewPending() {
  const imagePayload = (name) => ({
    path: `/review/${name}.png`,
    name: `${name}.png`,
    uri: `http://example.invalid/${name}.png`,
  });
  return {
    id: "vae-review-1",
    kind: "vae_review",
    payload: {
      items: [
        {
          path: "/images/first.png",
          name: "first.png",
          width: 640,
          height: 480,
          hf_loss: 0.12345,
          threshold: 0.2,
          diff_threshold: 12,
          flagged: false,
          initial_decision: "keep",
          views: {
            original: imagePayload("first-original"),
            vae: imagePayload("first-vae"),
            diff: imagePayload("first-diff"),
            hard: imagePayload("first-hard"),
          },
        },
        {
          path: "/images/second.png",
          name: "second.png",
          width: 320,
          height: 512,
          hf_loss: 0.456,
          threshold: 0.2,
          diff_threshold: 18,
          flagged: true,
          initial_decision: "replace",
          views: {
            original: imagePayload("second-original"),
            vae: imagePayload("second-vae"),
            diff: imagePayload("second-diff"),
            hard: imagePayload("second-hard"),
          },
        },
      ],
    },
  };
}

export function installMockImage() {
  class MockImage {
    constructor() {
      this.complete = false;
      this.width = 400;
      this.height = 300;
      this.onload = null;
    }

    set src(value) {
      this._src = value;
      this.complete = true;
      this.onload?.();
    }

    get src() {
      return this._src;
    }
  }

  global.Image = MockImage;
  window.Image = MockImage;
}

export function setCanvasClientRect(canvas, rect) {
  canvas.getBoundingClientRect = () => ({
    right: rect.left + rect.width,
    bottom: rect.top + rect.height,
    ...rect,
  });
}

export function drawBox(canvas, { start, end, pointerId = 7 }) {
  dispatchPointer(canvas, "pointerdown", {
    pointerId,
    button: 0,
    clientX: start[0],
    clientY: start[1],
  });
  dispatchPointer(canvas, "pointermove", {
    pointerId,
    clientX: end[0],
    clientY: end[1],
  });
  dispatchPointer(canvas, "pointerup", {
    pointerId,
    clientX: end[0],
    clientY: end[1],
  });
}

function canvasContext(contextCalls) {
  return {
    clearRect: (...args) => contextCalls.push(["clearRect", ...args]),
    drawImage: (...args) => contextCalls.push(["drawImage", ...args]),
    fillRect: (...args) => contextCalls.push(["fillRect", ...args]),
    fillText: (...args) => contextCalls.push(["fillText", ...args]),
    strokeRect: (...args) => contextCalls.push(["strokeRect", ...args]),
    set fillStyle(value) {
      contextCalls.push(["fillStyle", value]);
    },
    set font(value) {
      contextCalls.push(["font", value]);
    },
    set lineWidth(value) {
      contextCalls.push(["lineWidth", value]);
    },
    set strokeStyle(value) {
      contextCalls.push(["strokeStyle", value]);
    },
  };
}

function dispatchPointer(target, type, properties) {
  const event = new window.Event(type, { bubbles: true, cancelable: true });
  Object.entries(properties).forEach(([key, value]) => {
    Object.defineProperty(event, key, { value });
  });
  target.dispatchEvent(event);
}
