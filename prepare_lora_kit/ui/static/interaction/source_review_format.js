export function formatQuality(quality) {
  if (typeof quality === "string" && quality.trim()) {
    const numeric = Number(quality);
    return Number.isFinite(numeric) ? `${numeric}/100` : quality;
  }
  if (typeof quality !== "number" || !Number.isFinite(quality)) {
    return "not available";
  }
  return `${quality}/100`;
}

export function formatScoreValue(value) {
  if (value === null || value === undefined) {
    return "not available";
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return Number.isInteger(value) ? String(value) : value.toFixed(3);
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}
