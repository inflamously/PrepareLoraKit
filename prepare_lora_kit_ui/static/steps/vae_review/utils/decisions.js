export const VAE_DECISIONS = [
  { value: "keep", label: "Keep Input" },
  { value: "drop", label: "Drop Input" },
];

export function normalizeVaeDecision(decision) {
  return VAE_DECISIONS.some((entry) => entry.value === decision)
    ? decision
    : "keep";
}

export function optionForVaeDecision(decision) {
  const normalized = normalizeVaeDecision(decision);
  return VAE_DECISIONS.find((entry) => entry.value === normalized);
}
