import { escapeText } from "../../../core/dom.js";
import { CAPTION_VERDICTS } from "../utils/verdicts.js";

// The caption under test plus the verdict for it — one of each, for whichever
// image the filmstrip has selected. Built once; selecting another image swaps
// the textarea's value from the caption store rather than rebuilding the DOM,
// so focus and scroll position survive navigation.
export function createCaptionEditor(panel, { onInput, onVerdict } = {}) {
  panel.innerHTML = `
    <div class="caption-verify-editor__panel">
      <header class="caption-verify-editor__head">
        <span class="caption-verify-editor__label">
          // caption under test · <strong id="captionVerifyName">—</strong>
        </span>
        <span class="caption-verify-editor__count" id="captionVerifyCount"></span>
      </header>
      <textarea class="nf-input caption-verify-text" data-caption spellcheck="false"
                aria-label="Caption under test" title="Edit this caption"></textarea>
      <div id="captionVerifyStatus" class="caption-status"></div>
    </div>
    <div class="caption-verify-verdicts" role="group" aria-label="Verdict">
      ${CAPTION_VERDICTS.map(renderVerdictButton).join("")}
    </div>
    <p class="caption-verify-hint">1 / 2 / 3 to judge · → next</p>
  `;

  const nameEl = panel.querySelector("#captionVerifyName");
  const countEl = panel.querySelector("#captionVerifyCount");
  const textarea = panel.querySelector("textarea[data-caption]");
  const buttons = [...panel.querySelectorAll("[data-decision]")];

  textarea.addEventListener("input", () => onInput?.(textarea.value));
  buttons.forEach((button) => {
    button.addEventListener("click", () => onVerdict?.(button.dataset.decision));
  });

  const editor = {
    textarea,

    // `view` is null when the batch is empty: nothing to edit, nothing to judge.
    show(item, view = {}) {
      panel.classList.toggle("caption-verify-editor--empty", !item);
      // Assigned, never interpolated: a caption containing "</textarea>" would
      // otherwise break straight out of the element.
      textarea.value = item ? view.caption || "" : "";
      textarea.disabled = !item;
      textarea.placeholder = item ? "" : "No captions to verify";
      nameEl.textContent = item ? item.name : "—";
      buttons.forEach((button) => {
        button.disabled = !item;
      });
      editor.syncVerdict(view.verdict);
      editor.syncCounts(view);
    },

    syncVerdict(verdict) {
      buttons.forEach((button) => {
        button.setAttribute(
          "aria-pressed",
          String(button.dataset.decision === verdict),
        );
      });
    },

    // Token counts only exist once a render has come back for the text that is
    // on screen — an estimate here would be a guess about someone else's
    // tokenizer, so an unrendered (or edited) caption shows chars alone.
    syncCounts({ caption = "", tokens = null, edited = false } = {}) {
      panel.classList.toggle("caption-verify-editor--edited", Boolean(edited));
      const chars = `${caption.length} chars`;
      countEl.textContent =
        tokens === null || tokens === undefined
          ? chars
          : `${tokens} tokens · ${chars}`;
    },
  };
  return editor;
}

function renderVerdictButton(option) {
  const value = escapeText(option.value);
  return `
    <button type="button" class="nf-btn caption-verify-verdict caption-verify-verdict--${value}"
            data-decision="${value}">
      <span class="caption-verify-dot" aria-hidden="true"></span>${escapeText(option.label)}
    </button>
  `;
}
