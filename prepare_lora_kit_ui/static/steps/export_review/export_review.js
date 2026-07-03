import { api } from "../../core/api.js";
import { escapeText } from "../../core/dom.js";
import { state } from "../../+state/index.js";
import { closeModal, showModal } from "../../components/modal.js";

/**
 * ExportStep diff pre-step. Shows the added / modified / orphaned changes that
 * would be written to the export folder and lets the user uncheck individual
 * added/modified files before confirming. Orphaned files are read-only (they are
 * reported but never touched). "Skip export" resumes the run without writing.
 */
export function showExportReview(pending, { onSubmitted }) {
  const payload = pending.payload || {};
  const added = payload.added || [];
  const modified = payload.modified || [];
  const orphaned = payload.orphaned || [];
  const excluded = new Set();

  const modal = exportReviewModal(payload, { added, modified, orphaned });
  const confirmBtn = modal.querySelector("#confirmExport");
  const changeableTotal = added.length + modified.length;

  function updateConfirmLabel() {
    const willExport = changeableTotal - excluded.size;
    confirmBtn.textContent = willExport > 0 ? `Export ${willExport} file(s)` : "Export";
    confirmBtn.disabled = changeableTotal === 0 || willExport === 0;
  }

  modal.querySelectorAll("input[type=checkbox][data-rel]").forEach((cb) => {
    cb.addEventListener("change", () => {
      const rel = cb.getAttribute("data-rel");
      if (cb.checked) excluded.delete(rel);
      else excluded.add(rel);
      updateConfirmLabel();
    });
  });
  updateConfirmLabel();

  confirmBtn.addEventListener("click", async () => {
    await api().submit_interaction(state.jobId, pending.id, {
      confirmed: true,
      excluded: [...excluded],
    });
    closeModal();
    await onSubmitted();
  });

  modal.querySelector("#skipExport").addEventListener("click", async () => {
    await api().submit_interaction(state.jobId, pending.id, {
      confirmed: false,
      excluded: [],
    });
    closeModal();
    await onSubmitted();
  });

  showModal(modal);
}

function exportReviewModal(payload, { added, modified, orphaned }) {
  const modal = document.createElement("div");
  modal.className = "modal export-review-modal";
  modal.innerHTML = `
    <div class="modal-header">
      <div>
        <h2>Export finalized dataset</h2>
        <p>Copy image + caption pairs to <code>${escapeText(payload.target_dir || "")}</code></p>
      </div>
      <div class="modal-actions">
        <button class="ghost" id="skipExport">Skip export</button>
        <button class="primary" id="confirmExport">Export</button>
      </div>
    </div>
    <div class="export-review-body">
      ${changeSection("added", "Added", added)}
      ${changeSection("modified", "Modified", modified)}
      ${orphanSection(orphaned)}
      ${emptyMarkup(added.length + modified.length)}
    </div>
  `;
  return modal;
}

function changeSection(kind, label, entries) {
  if (!entries.length) return "";
  const rows = entries.map(rowMarkup).join("");
  return `
    <section class="export-section export-${kind}">
      <h3>${label} <span class="export-count">${entries.length}</span></h3>
      <ul class="export-list">${rows}</ul>
    </section>
  `;
}

function rowMarkup(entry) {
  const rel = entry.rel || "";
  const caption = entry.has_caption ? '<span class="export-cap">+ .txt</span>' : "";
  return `
    <li class="export-row">
      <label>
        <input type="checkbox" class="nf-check" data-rel="${escapeText(rel)}" checked />
        <span class="export-rel" title="${escapeText(rel)}">${escapeText(rel)}</span>
        ${caption}
      </label>
    </li>
  `;
}

function orphanSection(orphaned) {
  if (!orphaned.length) return "";
  const rows = orphaned
    .map((rel) => `<li class="export-row"><span class="export-rel">${escapeText(rel)}</span></li>`)
    .join("");
  return `
    <section class="export-section export-orphaned">
      <h3>Orphaned <span class="export-count">${orphaned.length}</span></h3>
      <p class="export-note">In the target but not in the final set — left untouched.</p>
      <ul class="export-list">${rows}</ul>
    </section>
  `;
}

function emptyMarkup(changeableTotal) {
  if (changeableTotal > 0) return "";
  return `<p class="export-empty">Nothing to export — the target already matches the finalized dataset.</p>`;
}
