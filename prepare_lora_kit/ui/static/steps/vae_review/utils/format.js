export function formatDimensions(item) {
  const width = Number(item.width);
  const height = Number(item.height);
  if (!Number.isFinite(width) || !Number.isFinite(height)) return "unknown size";
  return `${width}x${height}`;
}

export function formatNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "n/a";
  return number.toFixed(5).replace(/0+$/, "").replace(/\.$/, "");
}
