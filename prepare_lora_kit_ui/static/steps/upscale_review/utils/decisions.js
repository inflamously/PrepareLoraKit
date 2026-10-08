export const UPSCALE_DECISIONS = [
  { value: "upscale", label: "Upscale" },
  { value: "cleanup", label: "Clean Up → PNG (Same Size)" },
  { value: "skip", label: "Skip (Keep As-Is)" },
];

export function canUpscale(item) {
  const minSide = Number(item?.min_side);
  const target = Number(item?.target);
  if (!Number.isFinite(minSide) || !Number.isFinite(target)) return true;
  return minSide < target;
}

// Upscale only below the target, cleanup only for JPEGs; skip always applies.
export function decisionsFor(item) {
  return UPSCALE_DECISIONS.filter(({ value }) => {
    if (value === "upscale") return canUpscale(item);
    if (value === "cleanup") return Boolean(item?.is_jpeg);
    return true;
  });
}

export function normalizeUpscaleDecision(decision, item) {
  const allowed = (item ? decisionsFor(item) : UPSCALE_DECISIONS).map((entry) => entry.value);
  if (allowed.includes(decision)) return decision;
  if (item && allowed.includes(item.initial_decision)) return item.initial_decision;
  return allowed[0];
}

// "Keep size" still cleans a JPEG up to PNG; anything else stays untouched.
export function keepSizeDecision(item) {
  return item?.is_jpeg ? "cleanup" : "skip";
}

export function upscaleAllDecision(item) {
  return canUpscale(item) ? "upscale" : keepSizeDecision(item);
}

export function optionForUpscaleDecision(decision) {
  const normalized = normalizeUpscaleDecision(decision);
  return UPSCALE_DECISIONS.find((entry) => entry.value === normalized);
}
