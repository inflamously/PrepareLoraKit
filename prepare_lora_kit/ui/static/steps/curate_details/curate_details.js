import { api } from "../../core/api.js";
import { escapeText } from "../../core/dom.js";
import { state } from "../../core/state.js";
import { closeModal, showModal } from "../../components/modal.js";

export function showCurateDetails(pending, { onSubmitted }) {
  const payload = pending.payload || {};
  const modal = curateDetailsModal(payload);

  modal.querySelector("#continueCurateDetails").addEventListener("click", async () => {
    await api().submit_interaction(state.jobId, pending.id, { confirmed: true });
    closeModal();
    await onSubmitted();
  });

  showModal(modal);
}

function curateDetailsModal(payload) {
  const modal = document.createElement("div");
  modal.className = "modal curate-details-modal";
  modal.innerHTML = `
    <div class="modal-header">
      <div>
        <h2>Curate Details</h2>
        <p>${escapeText(subtitle(payload))}</p>
      </div>
      <button class="primary" id="continueCurateDetails">Continue</button>
    </div>
    <div class="curate-details-body">
      <section class="curate-coverage">
        ${coverageMarkup(payload)}
      </section>
      <aside class="curate-summary">
        <h3>Dataset Summary</h3>
        <dl class="curate-metrics">
          ${metricMarkup("Kept images", payload.summary?.kept_images)}
          ${metricMarkup("Duplicate pairs", payload.summary?.duplicate_pairs)}
          ${metricMarkup("Dropped duplicates", payload.summary?.dropped_duplicates)}
          ${metricMarkup("Occlusion flags", payload.summary?.occluded_flagged)}
          ${metricMarkup("PCA components", payload.coverage?.pca_components)}
        </dl>
        <div class="curate-report-path">
          <span>Report</span>
          <code>${escapeText(payload.report_path || "Not available")}</code>
        </div>
      </aside>
    </div>
  `;
  return modal;
}

function subtitle(payload) {
  const method = coverageLabel(payload);
  return method ? `Inspect ${method} coverage before continuing` : "Inspect curation results before continuing";
}

function coverageMarkup(payload) {
  if (!payload.coverage_image?.uri) {
    return `
      <div class="curate-coverage-missing">
        <strong>No coverage image</strong>
        <span>Coverage was skipped or failed for this run.</span>
      </div>
    `;
  }

  return `
    <figure>
      <img src="${escapeText(payload.coverage_image.uri)}" alt="Dataset coverage plot" />
      <figcaption>${escapeText(coverageLabel(payload))}</figcaption>
    </figure>
  `;
}

function coverageLabel(payload) {
  const method = String(payload.coverage_method || payload.coverage?.method || "").toLowerCase();
  if (method === "umap") return "CLIP PCA + UMAP";
  if (method === "pca") return "CLIP PCA";
  return "";
}

function metricMarkup(label, value) {
  return `
    <div>
      <dt>${escapeText(label)}</dt>
      <dd>${escapeText(formatMetric(value))}</dd>
    </div>
  `;
}

function formatMetric(value) {
  return Number.isFinite(Number(value)) ? String(Number(value)) : "0";
}
