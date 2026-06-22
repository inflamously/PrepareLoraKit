export const REVIEW_DECISIONS = [
  { value: "keep", label: "Keep" },
  { value: "reject", label: "Reject" },
  { value: "flag", label: "Flag" },
];

export function normalizeDecision(decision) {
  const found = optionForDecision(decision);
  return found ? found.value : REVIEW_DECISIONS[0].value;
}

export function optionForDecision(decision) {
  return REVIEW_DECISIONS.find((option) => option.value === decision);
}
