export function formatDimensions(item) {
  const width = Number(item.width);
  const height = Number(item.height);
  if (!Number.isFinite(width) || !Number.isFinite(height)) return "unknown size";
  return `${width}x${height}`;
}

export function formatPx(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${number}px` : "n/a";
}

export function formatPlannedAction(item) {
  switch (item.planned_action) {
    case "jpeg_cleanup":
      return "JPEG cleanup (downscale then re-upscale)";
    case "upscale":
      return "Upscale";
    default:
      return "Skip (pass-through)";
  }
}
