import { api } from "../../core/api.js";
import { state } from "../../+state/index.js";
import { renderCaptionStatus } from "../../caption/status.js";
import { closeModal, modalCancelButton, showModal } from "../../components/modal.js";
import { createCaptionEditor } from "./components/editor.js";
import { captionVerifyModal } from "./components/modal.js";
import {
  renderCaptionPreview,
  setPreviewStale,
  setPreviewWaitLabel,
} from "./components/preview.js";
import { captionVerifyTile, syncCaptionVerifyTiles } from "./components/strip.js";
import {
  buildSubmitValue,
  createCaptionStore,
  isEdited,
  readCaption,
  setCaption,
} from "./utils/captions.js";
import { createPreviewStore, isPreviewStale } from "./utils/previews.js";
import { CAPTION_VERDICTS, normalizeCaptionVerdict } from "./utils/verdicts.js";

export function showCaptionVerify(pending, { onSubmitted }) {
  new CaptionVerify(pending, onSubmitted).show();
}

class CaptionVerify {
  constructor(pending, onSubmitted) {
    this.pending = pending;
    this.onSubmitted = onSubmitted;
    this.items = pending.payload.items || [];
    this.settings = pending.payload.settings || {};

    this.verdicts = Object.fromEntries(
      this.items.map((item) => [
        item.path,
        normalizeCaptionVerdict(item.initial_verdict),
      ]),
    );
    this.captions = createCaptionStore(this.items);
    this.previews = createPreviewStore();
    this.reviewed = new Set();
    this.tilesByPath = new Map();
    // Starts at -1 so the first selectAt() in show() does real work — the
    // same-index early-return would otherwise skip the initial render.
    this.index = -1;
    this.selected = null;
    this.inflight = null;
    this.closed = false;
    this.elapsedSeconds = 0;
    this.ticker = null;

    this.modal = captionVerifyModal(this.items.length, this.settings);
    this.strip = this.modal.querySelector("#captionVerifyTiles");
    this.panel = this.modal.querySelector(".caption-verify-preview");
    this.progress = this.modal.querySelector("#captionVerifyProgress");
    this.auto = this.modal.querySelector("#captionVerifyAuto");

    // The job poll is the only channel a model load has: it blocks the bridge
    // call the modal is awaiting, so nothing comes back on that promise for as
    // long as the load runs.
    this.onJobStatus = (event) => {
      this.showJobStatus(event.detail?.caption_status);
    };
    this.onKeyDown = (event) => this.handleKey(event);
  }

  show() {
    this.editor = createCaptionEditor(
      this.modal.querySelector(".caption-verify-editor"),
      {
        onInput: (text) => this.onCaptionInput(text),
        onVerdict: (value) => this.setVerdict(this.selected, value),
      },
    );

    const tiles = this.items.map((item, index) => {
      const tile = captionVerifyTile(item, index, this.verdicts, {
        onSelect: () => this.selectAt(index),
        onVerdictChange: (changed) => this.onVerdictChange(changed),
      });
      this.tilesByPath.set(item.path, tile);
      return tile;
    });
    this.strip.replaceChildren(...tiles);

    if (this.items[0]) {
      // No auto-render on open: the user may never click Generate at all.
      this.selectAt(0, { autoRender: false });
    } else {
      this.editor.show(null);
      this.renderPreview();
    }

    this.modal
      .querySelector("#finishCaptionVerify")
      .addEventListener("click", () => this.submit());
    this.modal
      .querySelector("#captionVerifyPrev")
      .addEventListener("click", () => this.step(-1));
    this.modal
      .querySelector("#captionVerifyNext")
      .addEventListener("click", () => this.step(1));

    const actions = this.modal.querySelector(".modal-actions");
    // Cancelling closes the modal without going through submit(), so it has to
    // tear down the listeners this modal owns or they outlive it.
    actions.insertBefore(
      modalCancelButton(async () => {
        this.cleanup();
        await this.onSubmitted();
      }),
      actions.firstChild,
    );

    globalThis.addEventListener("plk:job-status", this.onJobStatus);
    document.addEventListener("keydown", this.onKeyDown);
    this.updateProgress();
    showModal(this.modal);
  }

  // --- selection ---------------------------------------------------------

  selectAt(index, { autoRender = true } = {}) {
    const item = this.items[index];
    if (!item || index === this.index) return;
    this.index = index;
    this.selected = item;
    this.tilesByPath.forEach((tile, path) => {
      tile.classList.toggle("selected", path === item.path);
    });
    this.tilesByPath
      .get(item.path)
      ?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
    this.showInEditor(item);
    this.renderPreview();

    // Clicking an image must not queue a GPU job per click: only render when
    // the user opted in, nothing is already running, and this image has no
    // render yet.
    if (
      autoRender &&
      this.auto?.checked &&
      !this.inflight &&
      !this.previews.has(item.path) &&
      item.has_caption
    ) {
      this.generate({ reroll: false });
    }
  }

  step(delta) {
    if (!this.items.length) return;
    const next = Math.min(
      this.items.length - 1,
      Math.max(0, this.index + delta),
    );
    this.selectAt(next);
  }

  showInEditor(item) {
    this.editor.show(item, {
      caption: readCaption(this.captions, item.path),
      verdict: this.verdicts[item.path],
      tokens: this.tokensFor(item.path),
      edited: isEdited(this.captions, item.path),
    });
  }

  // Counts only — never re-assigns the textarea's value, which would drop the
  // caret to the end of the text under whoever is typing.
  syncCounts() {
    const item = this.selected;
    if (!item) return;
    this.editor.syncCounts({
      caption: readCaption(this.captions, item.path),
      tokens: this.tokensFor(item.path),
      edited: isEdited(this.captions, item.path),
    });
  }

  // Only the encoder can count its own tokens, and only for the text it was
  // actually given: an edited caption has no token count until it is rendered.
  tokensFor(path) {
    const preview = this.previews.get(path);
    if (!preview || preview.token_count === null || preview.token_count === undefined) {
      return null;
    }
    return isPreviewStale(preview, readCaption(this.captions, path))
      ? null
      : preview.token_count;
  }

  // --- edits and verdicts ------------------------------------------------

  setVerdict(item, value) {
    if (!item) return;
    this.verdicts[item.path] = normalizeCaptionVerdict(value);
    this.onVerdictChange(item);
  }

  onVerdictChange(item) {
    this.reviewed.add(item.path);
    if (this.selected?.path === item.path) {
      this.editor.syncVerdict(this.verdicts[item.path]);
    }
    this.updateProgress();
  }

  onCaptionInput(text) {
    const item = this.selected;
    if (!item) return;
    setCaption(this.captions, item.path, text);
    this.syncCounts();
    setPreviewStale(
      this.panel,
      isPreviewStale(this.previews.get(item.path), text),
    );
    this.syncTiles();
  }

  handleKey(event) {
    if (event.defaultPrevented || this.closed) return;
    const typing = event.target === this.editor?.textarea;

    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      this.generate({ reroll: false });
      return;
    }
    // Everything below is a bare key, so it must never steal a keystroke that
    // belongs to the caption box.
    if (typing || event.ctrlKey || event.metaKey || event.altKey) return;

    const verdict = CAPTION_VERDICTS[["1", "2", "3"].indexOf(event.key)];
    if (verdict) {
      event.preventDefault();
      this.setVerdict(this.selected, verdict.value);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      this.step(1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      this.step(-1);
    }
  }

  // --- rendering ---------------------------------------------------------

  renderPreview() {
    const item = this.selected;
    const path = item?.path;
    renderCaptionPreview(
      this.panel,
      item,
      {
        preview: path ? this.previews.get(path) : null,
        status: path ? this.previews.status(path) : { state: "idle", error: "" },
        caption: path ? readCaption(this.captions, path) : "",
        elapsedSeconds: this.elapsedSeconds,
        jobStatus: state.job?.caption_status,
      },
      { onGenerate: (options) => this.generate(options) },
    );
    // The pane was just rebuilt, so its status element is empty again.
    this.showJobStatus(state.job?.caption_status);
  }

  showJobStatus(status) {
    if (this.closed) return;
    renderCaptionStatus(this.panel.querySelector("#captionVerifyStatus"), status);
    setPreviewWaitLabel(this.panel, {
      jobStatus: status,
      elapsedSeconds: this.elapsedSeconds,
    });
  }

  async generate({ reroll = false } = {}) {
    const item = this.selected;
    if (!item || !item.has_caption || this.inflight) return;

    // Capture the originating path: a slow render must land on the image it
    // was started for, not on whatever is selected when it returns.
    const path = item.path;
    const caption = readCaption(this.captions, path).trim();
    if (!caption) return;

    this.inflight = path;
    this.previews.setStatus(path, "generating");
    this.startTicker();
    this.renderPreview();

    try {
      const preview = await api().generate_caption_preview(
        state.jobId,
        path,
        caption,
        { reroll },
      );
      if (this.closed) return;
      this.previews.set(path, preview);
      this.previews.setStatus(path, "idle");
    } catch (error) {
      if (this.closed) return;
      this.previews.setStatus(path, "error", error?.message || String(error));
    } finally {
      this.stopTicker();
      this.inflight = null;
      if (!this.closed) {
        this.renderPreview();
        // A finished render is the only source of a token count.
        if (this.selected?.path === path) this.syncCounts();
      }
    }
  }

  // Without a local counter the modal looks frozen whenever the step emits no
  // incremental progress of its own — and the very first render of a run spends
  // most of its wait inside a model load that reports nothing for minutes.
  //
  // Only the label is retouched, never the whole pane: at one rebuild a second
  // a ten-minute load would re-parse both <img> tags six hundred times.
  startTicker() {
    this.elapsedSeconds = 0;
    this.stopTicker();
    this.ticker = globalThis.setInterval(() => {
      this.elapsedSeconds += 1;
      this.showJobStatus(state.job?.caption_status);
    }, 1000);
  }

  stopTicker() {
    if (this.ticker) {
      globalThis.clearInterval(this.ticker);
      this.ticker = null;
    }
  }

  updateProgress() {
    if (this.progress) {
      this.progress.textContent = `${this.reviewed.size} reviewed`;
    }
    this.syncTiles();
  }

  syncTiles() {
    syncCaptionVerifyTiles(this.tilesByPath, this.verdicts, {
      reviewed: this.reviewed,
      isEdited: (path) => isEdited(this.captions, path),
    });
  }

  cleanup() {
    this.closed = true;
    this.stopTicker();
    // These listeners live on globalThis/document; leaking them would fire for
    // every later job and swallow keystrokes meant for the next screen.
    globalThis.removeEventListener("plk:job-status", this.onJobStatus);
    document.removeEventListener("keydown", this.onKeyDown);
  }

  async submit() {
    const value = buildSubmitValue(this.items, this.verdicts, this.captions);
    this.cleanup();
    await api().submit_interaction(state.jobId, this.pending.id, value);
    closeModal();
    await this.onSubmitted();
  }
}
