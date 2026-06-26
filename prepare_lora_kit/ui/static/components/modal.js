import { api } from "../core/api.js";
import { $ } from "../core/dom.js";
import { state } from "../+state/index.js";

export function showModal(inner) {
  const layer = $("modalLayer");
  layer.replaceChildren(inner);
  layer.classList.remove("hidden");
}

export function closeModal() {
  const layer = $("modalLayer");
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
