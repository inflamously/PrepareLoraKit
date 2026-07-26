import { escapeText } from "../../../core/dom.js";
import { isPreviewStale } from "../utils/previews.js";

// The right pane: the real image beside what the text encoder made of its
// caption. The prompt is shown read-only here — the card holds the one
// editable copy, so there is no two-way sync to desync.
export function renderCaptionPreview(panel, item, view, handlers) {
  if (!item) {
    panel.innerHTML = `
      <div class="caption-verify-empty">
        <strong>No captions to verify</strong>
        <p>Run CaptionBboxStep first so every image has a caption sidecar.</p>
      </div>
    `;
    return;
  }

  const { preview, status, caption, elapsedSeconds } = view;
  const stale = isPreviewStale(preview, caption);

  panel.innerHTML = `
    <div class="caption-verify-compare">
      <figure>
        <figcaption>Source image</figcaption>
        ${renderImage(item.view_uri || item.uri, `${item.name} source`)}
      </figure>
      <figure class="caption-verify-generated">
        <figcaption>Rendered from caption</figcaption>
        ${renderGenerated(preview, status, elapsedSeconds, item)}
      </figure>
    </div>
    <div class="caption-verify-body">
      ${stale ? `<div class="caption-verify-stale">Caption edited since this render</div>` : ""}
      ${preview?.truncated ? renderTruncation(preview) : ""}
      <p class="caption-verify-prompt">${escapeText(preview ? preview.caption : caption) || "<no caption>"}</p>
      ${renderMeta(preview)}
      <div class="caption-verify-controls">
        <button class="primary" id="generateCaptionPreview" ${item.has_caption ? "" : "disabled"}>
          ${preview ? "Render again" : "Render from caption"}
        </button>
        <button class="nf-btn" id="rerollCaptionPreview" ${preview ? "" : "disabled"}>
          Re-roll seed
        </button>
      </div>
      <div id="captionVerifyStatus" class="caption-status"></div>
      ${status.error ? `<div class="caption-verify-error">${escapeText(status.error)}</div>` : ""}
    </div>
  `;

  panel
    .querySelector("#generateCaptionPreview")
    ?.addEventListener("click", () => handlers.onGenerate({ reroll: false }));
  panel
    .querySelector("#rerollCaptionPreview")
    ?.addEventListener("click", () => handlers.onGenerate({ reroll: true }));

  if (status.state === "generating") {
    panel.querySelector("#generateCaptionPreview")?.setAttribute("disabled", "");
    panel.querySelector("#rerollCaptionPreview")?.setAttribute("disabled", "");
  }
}

function renderImage(uri, alt) {
  if (!uri) {
    return `<div class="caption-verify-placeholder">no image</div>`;
  }
  return `<img src="${escapeText(uri)}" alt="${escapeText(alt)}" />`;
}

function renderGenerated(preview, status, elapsedSeconds, item) {
  if (status.state === "generating") {
    return `
      <div class="caption-verify-placeholder">
        <div class="caption-verify-spinner"></div>
        <span>Rendering… ${escapeText(String(elapsedSeconds))}s</span>
      </div>
    `;
  }
  if (status.state === "error") {
    return `<div class="caption-verify-placeholder">render failed</div>`;
  }
  if (!preview) {
    return `
      <div class="caption-verify-placeholder">
        ${item.has_caption ? "not rendered yet" : "no caption to render"}
      </div>
    `;
  }
  return renderImage(preview.view_uri || preview.uri, "rendered from caption");
}

// The single most reliable signal this step produces: a term past the encoder's
// context window was never seen at all, so a bad render says nothing about it.
function renderTruncation(preview) {
  return `
    <div class="caption-verify-truncated">
      Caption truncated at the encoder limit
      (${escapeText(String(preview.token_count ?? "?"))} tokens) — everything past
      the cut never reached the model.
    </div>
  `;
}

function renderMeta(preview) {
  if (!preview) return "";
  const parts = [
    ["seed", preview.seed],
    ["steps", preview.steps],
    ["guidance", preview.guidance],
    [
      "size",
      preview.width && preview.height ? `${preview.width}×${preview.height}` : null,
    ],
    ["took", preview.elapsed_ms ? `${(preview.elapsed_ms / 1000).toFixed(1)}s` : null],
  ].filter(([, value]) => value !== null && value !== undefined);

  return `
    <dl class="caption-verify-meta">
      ${parts
        .map(
          ([label, value]) =>
            `<div><dt>${escapeText(label)}</dt><dd>${escapeText(String(value))}</dd></div>`,
        )
        .join("")}
    </dl>
  `;
}
