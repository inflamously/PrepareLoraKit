import { api } from "../../core/api.js";
import { escapeText } from "../../core/dom.js";
import { state } from "../../+state/index.js";
import { closeModal, modalCancelButton, showModal } from "../../components/modal.js";

export function cropLossPercentage(image, bucket) {
  const sourceRatio = Number(image?.width) / Number(image?.height);
  const targetRatio = Number(bucket?.width) / Number(bucket?.height);
  if (!Number.isFinite(sourceRatio) || !Number.isFinite(targetRatio) || sourceRatio <= 0 || targetRatio <= 0) {
    return null;
  }
  const retained = Math.min(sourceRatio / targetRatio, targetRatio / sourceRatio);
  return Math.round((1 - retained) * 100);
}

export function showBucketPoolDetails(pending, { onSubmitted }) {
  const payload = pending.payload || {};
  const buckets = Array.isArray(payload.buckets) ? payload.buckets : [];
  let selectedBucket =
    buckets.find((bucket) => bucket.status === "thin" && bucket.count > 0) ||
    buckets.find((bucket) => bucket.count > 0) ||
    null;
  let selectedImage = selectedBucket?.images?.[0] || null;

  const modal = bucketPoolModal(payload);
  const bucketGrid = modal.querySelector(".bucket-pool-grid");
  const imageGrid = modal.querySelector(".bucket-image-grid");
  const detail = modal.querySelector(".bucket-pool-detail");

  const selectImage = (image) => {
    selectedImage = image;
    renderImages();
    renderDetail();
  };

  const selectBucket = (bucket) => {
    if (!bucket.count) return;
    selectedBucket = bucket;
    selectedImage = bucket.images?.[0] || null;
    renderBuckets();
    renderImages();
    renderDetail();
  };

  const renderBuckets = () => {
    bucketGrid.replaceChildren(
      ...buckets.map((bucket) => bucketCard(bucket, bucket === selectedBucket, selectBucket)),
    );
  };

  const renderImages = () => {
    const images = selectedBucket?.images || [];
    if (!images.length) {
      imageGrid.innerHTML = `<div class="bucket-panel-empty">No images are assigned to this bucket.</div>`;
      return;
    }
    imageGrid.replaceChildren(
      ...images.map((image) => imageCard(image, image === selectedImage, selectImage)),
    );
  };

  const renderDetail = () => {
    detail.innerHTML = detailMarkup(selectedBucket, selectedImage, payload.thin_threshold);
  };

  renderBuckets();
  renderImages();
  renderDetail();

  modal.querySelector("#continueBucketPoolDetails").addEventListener("click", async () => {
    await api().submit_interaction(state.jobId, pending.id, { confirmed: true });
    closeModal();
    await onSubmitted();
  });

  const actions = modal.querySelector(".modal-actions");
  actions.insertBefore(modalCancelButton(onSubmitted), actions.firstChild);
  showModal(modal);
}

function bucketPoolModal(payload) {
  const summary = payload.summary || {};
  const modal = document.createElement("div");
  modal.className = "modal bucket-pool-modal";
  modal.innerHTML = `
    <div class="modal-header">
      <div>
        <h2>Bucket Pools</h2>
        <p>${escapeText(summaryLine(summary))}</p>
      </div>
      <div class="modal-actions">
        <button class="primary" id="continueBucketPoolDetails">Continue</button>
      </div>
    </div>
    <div class="bucket-pool-workspace">
      <section class="bucket-pool-panel" aria-label="Configured buckets">
        <div class="bucket-panel-heading">
          <strong>Configured buckets</strong>
          <span>Thin means ≤ ${escapeText(payload.thin_threshold ?? 0)} images</span>
        </div>
        <div class="bucket-pool-grid"></div>
      </section>
      <section class="bucket-image-panel" aria-label="Assigned images">
        <div class="bucket-panel-heading">
          <strong>Assigned images</strong>
          <span>Select an image to inspect its crop</span>
        </div>
        <div class="bucket-image-grid"></div>
      </section>
      <section class="bucket-pool-detail" aria-live="polite"></section>
    </div>
    <div class="bucket-pool-footer">
      <span>Report</span>
      <code title="${escapeText(payload.report_path || "")}">${escapeText(payload.report_path || "Not available")}</code>
    </div>
  `;
  return modal;
}

function bucketCard(bucket, selected, onSelect) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `bucket-pool-card ${escapeText(bucket.status || "empty")}`;
  button.classList.toggle("selected", selected);
  button.disabled = !bucket.count;
  button.setAttribute("aria-pressed", String(selected));
  button.innerHTML = `
    <span class="bucket-card-shape" style="aspect-ratio:${Number(bucket.width)} / ${Number(bucket.height)}"></span>
    <span class="bucket-card-copy">
      <strong>${escapeText(dimensionLabel(bucket))}</strong>
      <small>${escapeText(countLabel(bucket.count))} · ${escapeText(statusLabel(bucket.status))}</small>
    </span>
  `;
  button.addEventListener("click", () => onSelect(bucket));
  return button;
}

function imageCard(image, selected, onSelect) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "bucket-image-card";
  button.classList.toggle("selected", selected);
  button.setAttribute("aria-pressed", String(selected));
  button.innerHTML = `
    <img loading="lazy" src="${escapeText(image.thumb_uri || image.uri || "")}" alt="" />
    <span title="${escapeText(image.name)}">${escapeText(image.name)}</span>
    <small>${escapeText(dimensionLabel(image))}</small>
  `;
  button.addEventListener("click", () => onSelect(image));
  return button;
}

function detailMarkup(bucket, image, thinThreshold) {
  if (!bucket || !image) {
    return `
      <div class="bucket-detail-empty">
        <strong>No bucket preview available</strong>
        <span>Select a populated bucket and image to inspect its training crop.</span>
      </div>
    `;
  }

  const loss = cropLossPercentage(image, bucket);
  const shape = previewShape(bucket);
  return `
    <div class="bucket-preview-grid">
      <figure>
        <div class="bucket-original-frame">
          <img src="${escapeText(image.view_uri || image.uri || "")}" alt="${escapeText(`${image.name} original`)}" />
        </div>
        <figcaption>Original · ${escapeText(dimensionLabel(image))}</figcaption>
      </figure>
      <figure>
        <div class="bucket-crop-stage">
          <div class="bucket-crop-shape" style="width:${shape.width}px;height:${shape.height}px">
            <img src="${escapeText(image.view_uri || image.uri || "")}" alt="${escapeText(`${image.name} bucket crop preview`)}" />
          </div>
        </div>
        <figcaption>Approximate bucket crop · ${escapeText(dimensionLabel(bucket))}</figcaption>
      </figure>
    </div>
    <div class="bucket-detail-copy">
      <div class="bucket-detail-title">
        <div>
          <strong title="${escapeText(image.name)}">${escapeText(image.name)}</strong>
          <small title="${escapeText(image.path)}">${escapeText(image.path)}</small>
        </div>
        <span class="bucket-status-pill ${escapeText(bucket.status)}">${escapeText(statusLabel(bucket.status))}</span>
      </div>
      <dl class="bucket-detail-metrics">
        <div><dt>Assigned bucket</dt><dd>${escapeText(dimensionLabel(bucket))}</dd></div>
        <div><dt>Images in pool</dt><dd>${escapeText(bucket.count)}</dd></div>
        <div><dt>Approx. crop</dt><dd>${loss === null ? "Unknown" : `${escapeText(loss)}%`}</dd></div>
      </dl>
      <p>${escapeText(bucketExplanation(bucket, thinThreshold))}</p>
      ${bucket.suggestion ? `<p class="bucket-suggestion"><strong>Possible adjustment:</strong> ${escapeText(bucket.suggestion)}</p>` : ""}
      <p class="bucket-preview-note">Assignment uses the closest aspect ratio. This preview scales to cover and center-crops; the trainer may choose a different crop position.</p>
    </div>
  `;
}

function previewShape(bucket) {
  const maxWidth = 300;
  const maxHeight = 300;
  const scale = Math.min(maxWidth / Number(bucket.width), maxHeight / Number(bucket.height));
  return {
    width: Math.max(1, Math.round(Number(bucket.width) * scale)),
    height: Math.max(1, Math.round(Number(bucket.height) * scale)),
  };
}

function summaryLine(summary) {
  const total = Number(summary.total_images) || 0;
  const populated = Number(summary.populated_buckets) || 0;
  const thin = Number(summary.thin_buckets) || 0;
  return `${total} images across ${populated} populated buckets · ${thin} thin pools`;
}

function bucketExplanation(bucket, thinThreshold) {
  if (bucket.status === "thin") {
    return `This pool has ${bucket.count} image(s), at or below the thin threshold of ${thinThreshold}. Small pools repeat the same examples more often and can provide less varied training signal.`;
  }
  return "This pool has enough images to clear the configured thin-bucket warning. The crop preview shows which edge content may be excluded during training.";
}

function dimensionLabel(value) {
  const width = Number(value?.width);
  const height = Number(value?.height);
  return Number.isFinite(width) && Number.isFinite(height) ? `${width}×${height}` : "Unknown size";
}

function countLabel(count) {
  return `${count} image${Number(count) === 1 ? "" : "s"}`;
}

function statusLabel(status) {
  if (status === "thin") return "Thin";
  if (status === "healthy") return "Healthy";
  return "Empty";
}
