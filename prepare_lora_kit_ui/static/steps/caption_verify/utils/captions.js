// Single source of truth for caption text while the modal is open. The
// <textarea> in each card mirrors into this store on every input event; the
// store is what feeds the render prompt, the stale check and the submit value.

export function createCaptionStore(items) {
  const store = new Map();
  for (const item of items || []) {
    const text = item.caption || "";
    store.set(item.path, { text, original: text });
  }
  return store;
}

export function readCaption(store, path) {
  return store.get(path)?.text ?? "";
}

export function setCaption(store, path, text) {
  const entry = store.get(path);
  if (entry) {
    entry.text = text;
  } else {
    store.set(path, { text, original: "" });
  }
}

export function isEdited(store, path) {
  const entry = store.get(path);
  if (!entry) return false;
  return entry.text.trim() !== entry.original.trim();
}

export function buildSubmitValue(items, verdicts, store) {
  const payload = {};
  for (const item of items || []) {
    payload[item.path] = {
      verdict: verdicts[item.path] || "correct",
      caption: readCaption(store, item.path),
      // The provider recomputes this server-side; it is sent for readability
      // of the request, never trusted as the source of truth.
      edited: isEdited(store, item.path),
    };
  }
  return { items: payload };
}
