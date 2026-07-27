import { escapeText } from "../../../core/dom.js";
import { formatElapsed } from "../../../caption/status.js";
import { isPreviewStale } from "../utils/previews.js";

// The right pane, top to bottom: the real image beside what the text encoder
// made of its caption, then the render controls, then anything the run wants to
// say about it. The caption itself is deliberately absent — the editor on the
// left owns the one copy, so there is nothing here to read twice or desync.
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

  const { preview, status, caption, elapsedSeconds, jobStatus } = view;

  panel.innerHTML = `
    <div class="caption-verify-compare">
      <figure>
        <figcaption>Source image</figcaption>
        ${renderImage(item.view_uri || item.uri, `${item.name} source`)}
      </figure>
      <figure class="caption-verify-generated">
        <figcaption>Rendered from caption</figcaption>
        ${renderGenerated(preview, status, elapsedSeconds, item, jobStatus)}
      </figure>
    </div>
    <div class="caption-verify-render">
      ${renderMeta(preview)}
      <div class="caption-verify-controls">
        <button class="primary" id="generateCaptionPreview" ${item.has_caption ? "" : "disabled"}>
          ${preview ? "Render again" : "Render from caption"}
        </button>
        <button class="nf-btn" id="rerollCaptionPreview" ${preview ? "" : "disabled"}>
          Re-roll seed
        </button>
        <p class="caption-verify-shortcut">
            <kbd>Ctrl</kbd> + <kbd>Enter</kbd> to generate
        </p>
      </div>
    </div>
    <div class="caption-verify-notices">
      <div id="captionVerifyStatus" class="caption-status hidden"></div>
      <div class="caption-verify-stale" ${isPreviewStale(preview, caption) ? "" : "hidden"}>
        Caption edited since this render
      </div>
      ${preview?.truncated ? renderTruncation(preview) : ""}
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

// Typing must not rebuild the pane — that would reload both <img> tags on every
// keystroke — so the staleness banner is toggled in place instead.
export function setPreviewStale(panel, stale) {
  const banner = panel.querySelector(".caption-verify-stale");
  if (banner) banner.hidden = !stale;
}

// Ticks the wait label once a second for the same reason: a model load runs for
// minutes, and rebuilding the pane every second would reload both <img> tags
// several hundred times over.
export function setPreviewWaitLabel(panel, { jobStatus, elapsedSeconds }) {
  const label = panel.querySelector("[data-wait-label]");
  if (label) label.textContent = waitLabel(jobStatus, elapsedSeconds);
}

// The first click of a run pays for the model load — up to ten minutes for a 9B
// FLUX.2 klein. Calling all of that "Rendering…" is not merely unhelpful, it is
// wrong about what the machine is doing and about how long it will last.
export function waitLabel(jobStatus, elapsedSeconds) {
  const clock = formatElapsed(elapsedSeconds);
  const phase = jobStatus?.phase;
  if (phase === "resolving") return `Preparing model… ${clock}`;
  if (phase === "loading") return `Loading model… ${clock}`;
  return `Rendering… ${clock}`;
}

function renderImage(uri, alt) {
  if (!uri) {
    return `<div class="caption-verify-placeholder">no image</div>`;
  }
  return `<img src="${escapeText(uri)}" alt="${escapeText(alt)}" />`;
}

function renderGenerated(preview, status, elapsedSeconds, item, jobStatus) {
  if (status.state === "generating") {
    return `
      <div class="caption-verify-placeholder">
        <div class="caption-verify-spinner"></div>
        <span data-wait-label>${escapeText(waitLabel(jobStatus, elapsedSeconds))}</span>
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

// Rendered even with no preview yet: the row is where the render settings live,
// and a strip that appears out of nowhere would shove the buttons down the pane
// the first time someone clicks Render.
function renderMeta(preview) {
  const size =
    preview?.width && preview?.height
      ? `${preview.width}×${preview.height}`
      : null;
  const parts = [
    ["seed", preview?.seed],
    ["steps", preview?.steps],
    ["guidance", preview?.guidance],
    ["size", size],
    ["took", preview?.elapsed_ms ? `${(preview.elapsed_ms / 1000).toFixed(1)}s` : null],
  ];

  return `
    <dl class="caption-verify-meta">
      ${parts
        .map(
          ([label, value]) =>
            `<div><dt>${escapeText(label)}</dt><dd>${escapeText(
              value === null || value === undefined ? "—" : String(value),
            )}</dd></div>`,
        )
        .join("")}
    </dl>
  `;
}
