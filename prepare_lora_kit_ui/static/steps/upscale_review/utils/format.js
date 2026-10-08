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

export function formatDecisionAction(item, decision) {
  switch (decision) {
    case "cleanup":
      return "JPEG cleanup → PNG, same size";
    case "upscale":
      return item.is_jpeg ? "Upscale → PNG" : "Upscale";
    default:
      return "Skip (pass-through)";
  }
}
