import { api } from "../../core/api.js";
import { state } from "../../+state/index.js";
import { renderCaptionStatus } from "../../caption/status.js";
import { closeModal, modalCancelButton, showModal } from "../../components/modal.js";
import { captionVerifyCard, syncCaptionVerifyCards } from "./components/card.js";
import { captionVerifyModal } from "./components/modal.js";
import { renderCaptionPreview } from "./components/preview.js";
import {
  buildSubmitValue,
  createCaptionStore,
  readCaption,
  setCaption,
} from "./utils/captions.js";
import { createPreviewStore } from "./utils/previews.js";
import { normalizeCaptionVerdict } from "./utils/verdicts.js";

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
    this.cardsByPath = new Map();
    // Starts null so the first selectItem() in show() does real work — the
    // same-path early-return would otherwise skip the initial render.
    this.selected = null;
    this.inflight = null;
    this.closed = false;
    this.elapsedSeconds = 0;
    this.ticker = null;

    this.modal = captionVerifyModal(this.items.length, this.settings);
    this.grid = this.modal.querySelector(".caption-verify-grid");
    this.panel = this.modal.querySelector(".caption-verify-preview");
    this.progress = this.modal.querySelector("#captionVerifyProgress");
    this.auto = this.modal.querySelector("#captionVerifyAuto");

    this.onJobStatus = (event) => {
      const el = this.modal.querySelector("#captionVerifyStatus");
      if (el) renderCaptionStatus(el, event.detail?.caption_status);
    };
  }

  show() {
    const cards = this.items.map((item) => {
      const card = captionVerifyCard(item, this.verdicts, {
        onSelect: (selected) => this.selectItem(selected),
        onVerdictChange: (changed) => this.onVerdictChange(changed),
        onCaptionInput: (changed, text) => this.onCaptionInput(changed, text),
      });
      this.cardsByPath.set(item.path, card);
      return card;
    });
    // Cards are built once and never re-rendered, so a <textarea> keeps its
    // edits for the modal's lifetime no matter how often selection changes.
    this.grid.replaceChildren(...cards);

    if (this.items[0]) {
      // No auto-render on open: the user may never click Generate at all.
      this.selectItem(this.items[0], { autoRender: false });
    } else {
      this.renderPreview();
    }

    this.modal
      .querySelector("#finishCaptionVerify")
      .addEventListener("click", () => this.submit());

    const actions = this.modal.querySelector(".modal-actions");
    actions.insertBefore(modalCancelButton(this.onSubmitted), actions.firstChild);

    globalThis.addEventListener("plk:job-status", this.onJobStatus);
    this.updateProgress();
    showModal(this.modal);
  }

  selectItem(item, { autoRender = true } = {}) {
    if (!item) return;
    if (this.selected?.path === item.path) return;
    this.selected = item;
    this.cardsByPath.forEach((card, path) => {
      card.classList.toggle("selected", path === item.path);
    });
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

  onVerdictChange(item) {
    this.reviewed.add(item.path);
    this.updateProgress();
    if (this.selected?.path === item.path) {
      this.renderPreview();
    }
  }

  onCaptionInput(item, text) {
    setCaption(this.captions, item.path, text);
    if (this.selected?.path === item.path) {
      this.renderPreview();
    }
  }

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
      },
      { onGenerate: (options) => this.generate(options) },
    );
    const statusEl = this.modal.querySelector("#captionVerifyStatus");
    if (statusEl) renderCaptionStatus(statusEl, state.job?.caption_status);
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
      if (!this.closed) this.renderPreview();
    }
  }

  // Without a local counter the modal looks frozen whenever the step emits no
  // incremental progress of its own.
  startTicker() {
    this.elapsedSeconds = 0;
    this.stopTicker();
    this.ticker = globalThis.setInterval(() => {
      this.elapsedSeconds += 1;
      if (!this.closed) this.renderPreview();
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
    syncCaptionVerifyCards(this.cardsByPath, this.verdicts);
  }

  cleanup() {
    this.closed = true;
    this.stopTicker();
    // The listener lives on globalThis; leaking it would fire for every later job.
    globalThis.removeEventListener("plk:job-status", this.onJobStatus);
  }

  async submit() {
    const value = buildSubmitValue(this.items, this.verdicts, this.captions);
    this.cleanup();
    await api().submit_interaction(state.jobId, this.pending.id, value);
    closeModal();
    await this.onSubmitted();
  }
}
