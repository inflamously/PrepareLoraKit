import { api } from "../core/api.js";
import { escapeText } from "../core/dom.js";
import { state } from "../core/state.js";
import { closeModal, showModal } from "./modal.js";

export function showAnnotator(pending, { onSubmitted }) {
  const image = pending.payload;
  const boxes = [];
  let selected = -1;
  const img = new Image();
  let scale = 1;
  let drawing = null;
  let activePointerId = null;

  const modal = document.createElement("div");
  modal.className = "modal";
  modal.innerHTML = `
    <div class="modal-header">
      <div>
        <h2>Annotate Regions</h2>
        <p>${escapeText(image.name)} · drag on the image to add a box</p>
      </div>
      <button class="primary" id="doneAnnotate">Done</button>
    </div>
    <div class="annotator">
      <div class="canvas-wrap"><canvas id="annotationCanvas"></canvas></div>
      <div class="box-panel">
        <div id="bboxStatus" class="bbox-status">No box selected</div>
        <button id="captionBox" class="secondary">Caption selected box</button>
        <button id="clearBoxes" class="secondary">Clear</button>
        <div id="boxList"></div>
      </div>
    </div>
    <div class="modal-footer">
      <button id="skipAllAnnotate" class="danger">Skip all remaining</button>
      <button id="skipAnnotate" class="secondary">Skip image</button>
    </div>
  `;

  const canvas = modal.querySelector("#annotationCanvas");
  const ctx = canvas.getContext("2d");
  const boxList = modal.querySelector("#boxList");
  const bboxStatus = modal.querySelector("#bboxStatus");
  const captionBoxButton = modal.querySelector("#captionBox");

  function normalizedFromPixels(rect) {
    return {
      x1: +(rect.x1 / canvas.width).toFixed(4),
      y1: +(rect.y1 / canvas.height).toFixed(4),
      x2: +(rect.x2 / canvas.width).toFixed(4),
      y2: +(rect.y2 / canvas.height).toFixed(4),
    };
  }

  function draw() {
    if (!img.complete || !canvas.width || !canvas.height) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    boxes.forEach((box, index) => {
      const x = box.x1 * canvas.width;
      const y = box.y1 * canvas.height;
      const w = (box.x2 - box.x1) * canvas.width;
      const h = (box.y2 - box.y1) * canvas.height;
      ctx.strokeStyle = index === selected ? "#5cc38a" : "#4ea1f3";
      ctx.lineWidth = index === selected ? 3 : 2;
      ctx.strokeRect(x, y, w, h);
      ctx.fillStyle = "rgba(0,0,0,0.72)";
      ctx.fillRect(x, y, Math.min(260, Math.max(90, w)), 22);
      ctx.fillStyle = "#edf0f2";
      ctx.font = "13px Segoe UI";
      ctx.fillText(box.label || `region ${index + 1}`, x + 5, y + 15);
    });
    if (drawing) {
      ctx.strokeStyle = "#d9a441";
      ctx.lineWidth = 2;
      const x = Math.min(drawing.x1, drawing.x2);
      const y = Math.min(drawing.y1, drawing.y2);
      ctx.strokeRect(
        x,
        y,
        Math.abs(drawing.x2 - drawing.x1),
        Math.abs(drawing.y2 - drawing.y1),
      );
    }
  }

  function renderBoxes() {
    const selectedBox = boxes[selected];
    bboxStatus.textContent = selectedBox
      ? `Selected: Region ${selected + 1}${selectedBox.label ? ` - ${selectedBox.label}` : ""}`
      : "No box selected";
    captionBoxButton.disabled = selected < 0;
    boxList.replaceChildren();
    boxes.forEach((box, index) => {
      const item = document.createElement("div");
      item.className = `box-item${index === selected ? " selected" : ""}`;
      item.innerHTML = `
        <strong>Region ${index + 1}</strong>
        <input value="${escapeText(box.label || "")}" placeholder="Description" />
        ${box.crop_name ? `<small>${escapeText(box.crop_name)}</small>` : ""}
        <button class="secondary">Select</button>
        <button class="danger">Delete</button>
      `;
      const input = item.querySelector("input");
      input.addEventListener("input", () => {
        box.label = input.value;
        draw();
      });
      item.querySelector(".secondary").addEventListener("click", () => {
        selected = index;
        draw();
        renderBoxes();
      });
      item.querySelector(".danger").addEventListener("click", () => {
        boxes.splice(index, 1);
        selected = -1;
        draw();
        renderBoxes();
      });
      boxList.appendChild(item);
    });
  }

  function canvasPoint(event) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return {
      x: Math.max(
        0,
        Math.min(canvas.width, (event.clientX - rect.left) * scaleX),
      ),
      y: Math.max(
        0,
        Math.min(canvas.height, (event.clientY - rect.top) * scaleY),
      ),
    };
  }

  function finishDrawing() {
    if (!drawing) return;
    const rect = {
      x1: Math.max(0, Math.min(drawing.x1, drawing.x2)),
      y1: Math.max(0, Math.min(drawing.y1, drawing.y2)),
      x2: Math.min(canvas.width, Math.max(drawing.x1, drawing.x2)),
      y2: Math.min(canvas.height, Math.max(drawing.y1, drawing.y2)),
    };
    drawing = null;
    activePointerId = null;
    if (rect.x2 - rect.x1 < 10 || rect.y2 - rect.y1 < 10) {
      draw();
      return;
    }
    const label =
      window.prompt("Describe this region", `region ${boxes.length + 1}`) || "";
    boxes.push({ ...normalizedFromPixels(rect), label });
    selected = boxes.length - 1;
    draw();
    renderBoxes();
  }

  function cancelDrawing() {
    drawing = null;
    activePointerId = null;
    draw();
  }

  function cleanupAnnotator() {
    window.removeEventListener("blur", cancelDrawing);
  }

  async function submitAnnotator(value) {
    cleanupAnnotator();
    await api().submit_interaction(state.jobId, pending.id, value);
    closeModal();
    await onSubmitted();
  }

  canvas.addEventListener("pointerdown", (event) => {
    if (event.button != null && event.button !== 0) return;
    canvas.setPointerCapture(event.pointerId);
    activePointerId = event.pointerId;
    const p = canvasPoint(event);
    drawing = { x1: p.x, y1: p.y, x2: p.x, y2: p.y };
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!drawing || event.pointerId !== activePointerId) return;
    const p = canvasPoint(event);
    drawing.x2 = p.x;
    drawing.y2 = p.y;
    draw();
  });
  canvas.addEventListener("pointerup", (event) => {
    if (event.pointerId !== activePointerId) return;
    if (canvas.hasPointerCapture(event.pointerId)) {
      canvas.releasePointerCapture(event.pointerId);
    }
    finishDrawing();
  });
  canvas.addEventListener("pointercancel", cancelDrawing);
  window.addEventListener("blur", cancelDrawing);

  modal.querySelector("#captionBox").addEventListener("click", async () => {
    if (selected < 0) return alert("Select a box first.");
    captionBoxButton.disabled = true;
    captionBoxButton.textContent = "Captioning...";
    try {
      const result = await api().caption_region(
        state.jobId,
        image.path,
        boxes[selected],
      );
      boxes[selected].label = result.caption || boxes[selected].label;
      if (result.crop_path) boxes[selected].crop_path = result.crop_path;
      if (result.crop_name) boxes[selected].crop_name = result.crop_name;
      if (result.sidecar_path)
        boxes[selected].sidecar_path = result.sidecar_path;
    } finally {
      captionBoxButton.textContent = "Caption selected box";
      renderBoxes();
      draw();
    }
  });
  modal.querySelector("#clearBoxes").addEventListener("click", () => {
    boxes.splice(0, boxes.length);
    selected = -1;
    renderBoxes();
    draw();
  });
  modal.querySelector("#doneAnnotate").addEventListener("click", async () => {
    await submitAnnotator({
      annotations: boxes.filter((box) => (box.label || "").trim()),
      skipped: false,
      skip_all: false,
    });
  });
  modal.querySelector("#skipAnnotate").addEventListener("click", async () => {
    await submitAnnotator({
      annotations: [],
      skipped: true,
      skip_all: false,
    });
  });
  modal
    .querySelector("#skipAllAnnotate")
    .addEventListener("click", async () => {
      await submitAnnotator({
        annotations: [],
        skipped: true,
        skip_all: true,
      });
    });

  img.onload = () => {
    const maxW = Math.min(820, window.innerWidth - 450);
    const maxH = Math.min(640, window.innerHeight - 220);
    scale = Math.min(maxW / img.width, maxH / img.height, 1);
    canvas.width = Math.max(1, Math.round(img.width * scale));
    canvas.height = Math.max(1, Math.round(img.height * scale));
    draw();
    renderBoxes();
  };
  img.src = image.uri;
  showModal(modal);
}
