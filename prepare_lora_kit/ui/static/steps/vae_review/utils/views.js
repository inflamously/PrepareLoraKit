export const VAE_VIEWS = [
  { value: "original", label: "Original" },
  { value: "vae", label: "VAE" },
  { value: "diff", label: "Diff" },
  { value: "hard", label: "Hard Mask" },
];

export function normalizeVaeView(item, view) {
  return item?.views?.[view] ? view : "original";
}
