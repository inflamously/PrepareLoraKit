// Pure rendering helpers for the bbox annotation canvas. Each takes the 2D
// context plus the data it needs and draws; none close over canvas/img state,
// so they stay easy to read and reason about in isolation.

const STROKE = "#4ea1f3";
const STROKE_SELECTED = "#5cc38a";
const STROKE_PENDING = "#d9a441";

// Draw a single normalized box (coords in 0–1) plus its label chip. When
// `highlight` is set the outline glows gold to flag a region still missing a
// caption.
export function drawBox(ctx, box, index, selected, width, height, highlight) {
  const x = box.x1 * width;
  const y = box.y1 * height;
  const w = (box.x2 - box.x1) * width;
  const h = (box.y2 - box.y1) * height;
  const isSelected = index === selected;

  if (highlight) {
    // save/restore so the glow shadow doesn't bleed onto the label chip below.
    ctx.save();
    ctx.strokeStyle = "#ffe000"; // matches --accent gold
    ctx.lineWidth = 3;
    ctx.shadowColor = "rgba(255,224,0,0.9)";
    ctx.shadowBlur = 16;
    ctx.strokeRect(x, y, w, h);
    ctx.restore();
  } else {
    ctx.strokeStyle = isSelected ? STROKE_SELECTED : STROKE;
    ctx.lineWidth = isSelected ? 3 : 2;
    ctx.strokeRect(x, y, w, h);
  }

  ctx.fillStyle = "rgba(0,0,0,0.72)";
  ctx.fillRect(x, y, Math.min(260, Math.max(90, w)), 22);
  ctx.fillStyle = "#edf0f2";
  ctx.font = "13px Segoe UI";
  ctx.fillText(box.label || `region ${index + 1}`, x + 5, y + 15);
}

// Draw the in-progress drag rect (corners in any order, pixel coords).
export function drawPendingRect(ctx, drawing) {
  ctx.strokeStyle = STROKE_PENDING;
  ctx.lineWidth = 2;
  ctx.strokeRect(
    Math.min(drawing.x1, drawing.x2),
    Math.min(drawing.y1, drawing.y2),
    Math.abs(drawing.x2 - drawing.x1),
    Math.abs(drawing.y2 - drawing.y1),
  );
}
