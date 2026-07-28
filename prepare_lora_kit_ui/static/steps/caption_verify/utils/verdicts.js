// The three-way rubric this step exists to answer: does the text encoder know
// this term, know it only vaguely, or bind it to something else entirely?
export const CAPTION_VERDICTS = [
  { value: "correct", label: "Renders correctly" }, // encoder knows it — keep
  { value: "generic", label: "Renders generic" }, // weak embedding — use plain geometry
  { value: "wrong", label: "Renders wrong" }, // bound elsewhere — actively harmful
];

const VALUES = new Set(CAPTION_VERDICTS.map((option) => option.value));

export const DEFAULT_CAPTION_VERDICT = "correct";

// "correct" is the no-op default: reviewCard lands every item on one of the
// options at construction, so the default must mean "nothing to change".
export function normalizeCaptionVerdict(value) {
  return VALUES.has(value) ? value : "correct";
}

export function captionVerdictLabel(value) {
  const match = CAPTION_VERDICTS.find(
    (option) => option.value === normalizeCaptionVerdict(value),
  );
  return match ? match.label : "";
}
