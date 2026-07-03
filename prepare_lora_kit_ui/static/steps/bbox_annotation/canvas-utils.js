// Pure geometry helpers for the bbox annotation canvas. They take everything
// they need as arguments (no closure over canvas/img state) so they stay easy
// to read and unit-test.

// Convert a pixel-space rect into image-relative normalized coords (0–1),
// rounded to 4 decimals — the on-disk box format.
export function normalizedFromPixels(rect, width, height) {
  return {
    x1: +(rect.x1 / width).toFixed(4),
    y1: +(rect.y1 / height).toFixed(4),
    x2: +(rect.x2 / width).toFixed(4),
    y2: +(rect.y2 / height).toFixed(4),
  };
}

// Map a pointer event to canvas-internal pixel coordinates, clamped to the
// canvas bounds. Uses getBoundingClientRect so it stays correct regardless of
// scroll position or CSS scaling of the canvas element.
export function canvasPointFromEvent(canvas, event) {
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  return {
    x: Math.max(0, Math.min(canvas.width, (event.clientX - rect.left) * scaleX)),
    y: Math.max(0, Math.min(canvas.height, (event.clientY - rect.top) * scaleY)),
  };
}

// Normalize an in-progress drag (corners in any order) into an ordered,
// clamped {x1,y1,x2,y2} pixel rect.
export function clampRect(drawing, width, height) {
  return {
    x1: Math.max(0, Math.min(drawing.x1, drawing.x2)),
    y1: Math.max(0, Math.min(drawing.y1, drawing.y2)),
    x2: Math.min(width, Math.max(drawing.x1, drawing.x2)),
    y2: Math.min(height, Math.max(drawing.y1, drawing.y2)),
  };
}

// Compute the on-screen canvas size for an image that must fit the available
// viewport, never upscaling past 1:1.
export function fitCanvasSize(imgWidth, imgHeight, viewportWidth, viewportHeight) {
  const maxW = Math.min(820, viewportWidth - 450);
  const maxH = Math.min(640, viewportHeight - 220);
  const scale = Math.min(maxW / imgWidth, maxH / imgHeight, 1);
  return {
    width: Math.max(1, Math.round(imgWidth * scale)),
    height: Math.max(1, Math.round(imgHeight * scale)),
  };
}
