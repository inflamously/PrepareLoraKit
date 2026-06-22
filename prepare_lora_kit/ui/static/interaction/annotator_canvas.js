export function createAnnotationCanvas({
  canvas,
  img,
  boxes,
  getSelected,
  setSelected,
  onBoxesChanged,
}) {
  const ctx = canvas.getContext("2d");
  let drawing = null;
  let activePointerId = null;

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
      ctx.strokeStyle = index === getSelected() ? "#5cc38a" : "#4ea1f3";
      ctx.lineWidth = index === getSelected() ? 3 : 2;
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
      globalThis.prompt("Describe this region", `region ${boxes.length + 1}`) || "";
    boxes.push({ ...normalizedFromPixels(rect), label });
    setSelected(boxes.length - 1);
    onBoxesChanged();
  }

  function cancelDrawing() {
    drawing = null;
    activePointerId = null;
    draw();
  }

  function resizeToImage() {
    const maxW = Math.min(820, globalThis.innerWidth - 450);
    const maxH = Math.min(640, globalThis.innerHeight - 220);
    const scale = Math.min(maxW / img.width, maxH / img.height, 1);
    canvas.width = Math.max(1, Math.round(img.width * scale));
    canvas.height = Math.max(1, Math.round(img.height * scale));
    onBoxesChanged();
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
  globalThis.addEventListener("blur", cancelDrawing);

  return {
    draw,
    resizeToImage,
    cleanup() {
      globalThis.removeEventListener("blur", cancelDrawing);
    },
  };
}
