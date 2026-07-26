// Per-image render cache and status, keyed by path.
//
// Keying by path (rather than "the selected item") is what lets a slow render
// finish safely after the user has moved on: the result lands on the image it
// was started for, never on whatever happens to be selected when it returns.

export function createPreviewStore() {
  const previews = new Map();
  const statuses = new Map();

  return {
    get(path) {
      return previews.get(path) || null;
    },
    set(path, preview) {
      previews.set(path, preview);
    },
    has(path) {
      return previews.has(path);
    },
    status(path) {
      return statuses.get(path) || { state: "idle", error: "" };
    },
    setStatus(path, state, error = "") {
      statuses.set(path, { state, error });
    },
  };
}

// True when the caption has been edited since the render that is on screen —
// the preview then shows what an older caption meant, not the current one.
export function isPreviewStale(preview, caption) {
  if (!preview) return false;
  return (preview.caption || "").trim() !== (caption || "").trim();
}
