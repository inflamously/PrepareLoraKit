export const UPSCALE_DECISIONS = [
  { value: "upscale", label: "Upscale / Clean Up" },
  { value: "skip", label: "Skip (Keep As-Is)" },
];

export function normalizeUpscaleDecision(decision) {
  return UPSCALE_DECISIONS.some((entry) => entry.value === decision)
    ? decision
    : "upscale";
}

export function optionForUpscaleDecision(decision) {
  const normalized = normalizeUpscaleDecision(decision);
  return UPSCALE_DECISIONS.find((entry) => entry.value === normalized);
}
