import { api } from "../core/api.js";
import { $ } from "../core/dom.js";
import { state } from "../+state/index.js";

// The single backdrop-dismiss listener currently bound to the shared #modalLayer,
// or null. Tracked here so it is always torn down on the next showModal/closeModal
// instead of lingering on the persistent layer element. A leaked listener would
// otherwise dismiss whatever modal opens next (e.g. the pre-step config strip).
let backdropHandler = null;

function detachBackdrop(layer) {
  if (!backdropHandler) return;
  layer.removeEventListener("click", backdropHandler);
  backdropHandler = null;
}

// Show `inner` in the shared modal layer. Pass `onBackdrop` to make clicks on the
// dimmed layer (outside the dialog itself) dismiss it; only that single listener is
// kept, and it is removed by the next showModal/closeModal so it can never outlive
// its modal.
export function showModal(inner, { onBackdrop } = {}) {
  const layer = $("modalLayer");
  detachBackdrop(layer);
  layer.replaceChildren(inner);
  layer.classList.remove("hidden");
  if (onBackdrop) {
    backdropHandler = (event) => {
      if (event.target === layer) onBackdrop();
    };
    layer.addEventListener("click", backdropHandler);
  }
}

export function closeModal() {
  const layer = $("modalLayer");
  detachBackdrop(layer);
  layer.classList.add("hidden");
  layer.replaceChildren();
}

// Shared Cancel button for the mid-run, pre-step modals. The run thread is paused
// inside `request_input` waiting on the pending interaction; cancelling the job
// makes that wait raise `CancelledRun`, aborting the whole run so the user is
// never forced to continue. `onSubmitted` is the same poll callback the modal's
// continue action uses, so the UI refreshes to the cancelled state afterwards.
export function modalCancelButton(onSubmitted) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "danger modal-cancel";
  button.id = "modalCancel";
  button.textContent = "Cancel run";
  button.addEventListener("click", async () => {
    button.disabled = true;
    button.textContent = "Cancelling...";
    try {
      if (state.jobId) await api().cancel_job(state.jobId);
    } finally {
      closeModal();
      if (onSubmitted) await onSubmitted();
    }
  });
  return button;
}
