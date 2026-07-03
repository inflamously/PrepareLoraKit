import { isUncaptioned } from "./bbox-annotation-utils.js";

// Pure state/payload/validation helpers for the multi-image annotation
// workspace, kept out of the Annotator class so they stay easy to unit-test.

// Build the per-image working state from the batch interaction payload. Each
// state owns its own boxes + selection so navigating between images never leaks
// one image's edits onto another.
export function createImageStates(payload) {
  const images = Array.isArray(payload?.images) ? payload.images : [];
  return images.map((image) => ({
    path: image.path,
    name: image.name,
    uri: image.uri,
    // Downscaled variants served by the media endpoint: a small thumb for the strip and a
    // viewport-sized view for the canvas. Fall back to the full uri (e.g. file:// fixtures).
    thumbUri: image.thumb_uri || image.uri,
    viewUri: image.view_uri || image.uri,
    boxes: Array.isArray(image.annotations)
      ? image.annotations.map((box) => ({ ...box }))
      : [],
    selected: -1,
    highlightMissing: false,
    // Pre-captioned on a previous run; its boxes were reloaded from disk.
    done: Boolean(image.done),
    // Set once the user draws/edits/captions a box here, so an untouched done
    // image is kept (not re-captioned) while an edited one is re-captioned.
    dirty: false,
    // Explicit "skip image" — never caption this one.
    skipped: false,
    loaded: false,
  }));
}

// Whether an image should be left un-captioned on submit. Explicit skip wins;
// otherwise an edited image is captioned and an untouched done image is kept.
export function effectiveSkipped(state) {
  if (state.skipped) return true;
  if (state.dirty) return false;
  return Boolean(state.done);
}

// The submit payload mirrors UiInteractionProvider.annotate_dataset's expected
// answer: a per-path map of {annotations, skipped} plus a batch skip_all flag.
export function buildSubmitValue(states, { skipAll = false, activeIndex = 0 } = {}) {
  const images = {};
  states.forEach((state, index) => {
    const annotations = state.boxes.filter((box) => (box.label || "").trim());
    let skipped;
    if (skipAll) {
      // Skip-all-remaining: caption the current image, honor edits already made
      // this session, and skip every other still-untouched image.
      skipped = index === activeIndex ? false : state.dirty ? effectiveSkipped(state) : true;
    } else {
      skipped = effectiveSkipped(state);
    }
    images[state.path] = { annotations, skipped };
  });
  return { images, skip_all: skipAll };
}

// First image that will be captioned (not skipped) yet still has an
// un-captioned box — used to block Done and jump the user to the offender.
// Skipped images are ignored: their boxes are never sent to the captioner.
export function firstUncaptionedIndex(states) {
  return states.findIndex(
    (state) => !effectiveSkipped(state) && state.boxes.some(isUncaptioned),
  );
}

// Badge state for a thumbnail (active outlining is applied separately).
export function imageStripState(state) {
  if (state.skipped) return "skipped";
  if (state.done && !state.dirty) return "done";
  if (state.boxes.length) return "has-boxes";
  return "empty";
}
