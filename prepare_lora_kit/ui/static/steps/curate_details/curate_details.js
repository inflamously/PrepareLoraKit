import { api } from "../../core/api.js";
import { escapeText } from "../../core/dom.js";
import { state } from "../../+state/index.js";
import { closeModal, modalCancelButton, showModal } from "../../components/modal.js";

export const HOVER_DELAY_MS = 500;
const HOVER_HIT_RADIUS_PX = 12;

export function showCurateDetails(pending, { onSubmitted }) {
  const payload = pending.payload || {};
  const modal = curateDetailsModal(payload);
  const cancelHover = wireCoverageHover(modal, payload);

  modal.querySelector("#continueCurateDetails").addEventListener("click", async () => {
    cancelHover();
    await api().submit_interaction(state.jobId, pending.id, { confirmed: true });
    closeModal();
    await onSubmitted();
  });

  const actions = modal.querySelector(".modal-actions");
  actions.insertBefore(
    modalCancelButton(async () => {
      cancelHover();
      await onSubmitted();
    }),
    actions.firstChild,
  );

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
      <div class="modal-actions">
        <button class="primary" id="continueCurateDetails">Continue</button>
      </div>
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
      <div class="curate-coverage-frame">
        <img src="${escapeText(payload.coverage_image.uri)}" alt="Dataset coverage plot" />
      </div>
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

/**
 * Wires hover-to-reveal-thumbnail behavior onto the coverage plot dots and
 * returns a cleanup function that cancels any pending/visible tooltip — call
 * it before the modal closes so a scheduled `setTimeout` never touches a
 * detached tooltip.
 *
 * A no-op cleanup is returned when there's no image or no per-point data
 * (older reports, or coverage generation failed) so behavior is unchanged.
 */
function wireCoverageHover(modal, payload) {
  const points = payload.coverage?.points;
  const frame = modal.querySelector(".curate-coverage-frame");
  const img = frame?.querySelector("img");
  if (!frame || !img || !points?.length) return () => {};

  const tooltip = document.createElement("div");
  tooltip.className = "curate-coverage-tooltip hidden";
  tooltip.innerHTML = `
    <img class="curate-coverage-tooltip-thumb" alt="" />
    <span class="curate-coverage-tooltip-label"></span>
  `;
  frame.appendChild(tooltip);
  const tooltipImg = tooltip.querySelector(".curate-coverage-tooltip-thumb");
  const tooltipLabel = tooltip.querySelector(".curate-coverage-tooltip-label");

  let armedPoint = null;
  let timer = null;

  function clearArmed() {
    armedPoint = null;
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    tooltip.classList.add("hidden");
  }

  function positionTooltip(x, y) {
    const maxLeft = frame.clientWidth - tooltip.offsetWidth - 4;
    const maxTop = frame.clientHeight - tooltip.offsetHeight - 4;
    tooltip.style.left = `${Math.max(4, Math.min(x + 14, maxLeft))}px`;
    tooltip.style.top = `${Math.max(4, Math.min(y + 14, maxTop))}px`;
  }

  img.addEventListener("mousemove", (event) => {
    const rect = containedImageRect(img);
    const point = findHoveredPoint(points, event.offsetX, event.offsetY, rect, HOVER_HIT_RADIUS_PX);
    img.style.cursor = point ? "pointer" : "";
    if (point === armedPoint) {
      if (point && !tooltip.classList.contains("hidden")) {
        positionTooltip(event.offsetX, event.offsetY);
      }
      return;
    }

    clearArmed();
    if (!point) return;
    armedPoint = point;
    const { offsetX, offsetY } = event;
    timer = setTimeout(() => {
      tooltipImg.src = point.thumb_uri || point.uri;
      tooltipLabel.textContent = point.name;
      tooltip.classList.remove("hidden");
      positionTooltip(offsetX, offsetY);
    }, HOVER_DELAY_MS);
  });

  img.addEventListener("mouseleave", () => {
    img.style.cursor = "";
    clearArmed();
  });

  return clearArmed;
}

/**
 * The visible content rect of an `<img>` rendered with `object-fit: contain`,
 * in coordinates relative to the image element's own box (matching
 * `MouseEvent.offsetX/offsetY`). Letterboxing happens when the element's box
 * aspect ratio (driven by CSS width/max-height) doesn't match the image's
 * natural aspect ratio.
 */
export function containedImageRect(img) {
  const boxWidth = img.clientWidth;
  const boxHeight = img.clientHeight;
  const naturalWidth = img.naturalWidth;
  const naturalHeight = img.naturalHeight;
  if (!boxWidth || !boxHeight || !naturalWidth || !naturalHeight) {
    return { left: 0, top: 0, width: boxWidth, height: boxHeight };
  }
  const scale = Math.min(boxWidth / naturalWidth, boxHeight / naturalHeight);
  const width = naturalWidth * scale;
  const height = naturalHeight * scale;
  return { left: (boxWidth - width) / 2, top: (boxHeight - height) / 2, width, height };
}

/**
 * The coverage point nearest the cursor, within `hitRadiusPx`, or null when
 * the cursor is outside the rendered image content (letterboxed margin) or
 * too far from every point. `offsetX`/`offsetY` and `rect` must share the
 * same coordinate space (the image element's own box).
 */
export function findHoveredPoint(points, offsetX, offsetY, rect, hitRadiusPx) {
  if (!points?.length || !rect.width || !rect.height) return null;
  if (
    offsetX < rect.left ||
    offsetX > rect.left + rect.width ||
    offsetY < rect.top ||
    offsetY > rect.top + rect.height
  ) {
    return null;
  }

  let nearest = null;
  let nearestDist = Infinity;
  for (const point of points) {
    const px = rect.left + (point.x_pct / 100) * rect.width;
    const py = rect.top + (point.y_pct / 100) * rect.height;
    const dist = Math.hypot(px - offsetX, py - offsetY);
    if (dist < nearestDist) {
      nearestDist = dist;
      nearest = point;
    }
  }
  return nearestDist <= hitRadiusPx ? nearest : null;
}
