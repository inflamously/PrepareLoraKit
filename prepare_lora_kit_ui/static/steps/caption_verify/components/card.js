import { escapeText } from "../../../core/dom.js";
import { reviewCard, syncReviewCards } from "../../../components/review_card.js";
import { CAPTION_VERDICTS, normalizeCaptionVerdict } from "../utils/verdicts.js";

export function captionVerifyCard(
  item,
  verdicts,
  { onSelect, onVerdictChange, onCaptionInput } = {},
) {
  const card = reviewCard(item, verdicts, {
    className: "caption-verify-card",
    title: "Left-click card to preview; right-click card to cycle verdict",
    decisionOptions: CAPTION_VERDICTS,
    normalizeDecision: normalizeCaptionVerdict,
    renderBody: renderCaptionVerifyCardBody,
    onSelect,
    onDecisionChange: onVerdictChange,
  });

  const textarea = card.querySelector("textarea[data-caption]");

  // Assigned imperatively, never interpolated into the template above.
  // escapeText does not escape "'" and, more importantly, a caption containing
  // "</textarea>" would otherwise break out of the element entirely. Setting
  // .value after innerHTML removes the question.
  textarea.value = item.caption || "";

  // reviewCard binds click (select) and contextmenu (cycle verdict, with
  // preventDefault) on the CARD. Both are wrong inside a text field: the
  // right-click would kill the native copy/paste menu *and* silently flip the
  // verdict. Stop the bubble here so those card-level listeners never see it.
  for (const type of ["click", "pointerdown", "contextmenu", "dblclick"]) {
    textarea.addEventListener(type, (event) => event.stopPropagation());
  }
  textarea.addEventListener("input", () => {
    card.classList.toggle(
      "caption-verify-card--edited",
      textarea.value.trim() !== (item.caption || "").trim(),
    );
    onCaptionInput?.(item, textarea.value);
  });

  if (!item.has_caption) {
    card.classList.add("caption-verify-card--nocaption");
  }
  return card;
}

export function syncCaptionVerifyCards(cardsByPath, verdicts) {
  syncReviewCards(cardsByPath, verdicts, {
    decisionOptions: CAPTION_VERDICTS,
    normalizeDecision: normalizeCaptionVerdict,
  });
}

function renderCaptionVerifyCardBody(item) {
  const thumb = item.thumb_uri || item.uri;
  return `
    <figure class="caption-verify-thumb">
      ${
        thumb
          ? `<img loading="lazy" src="${escapeText(thumb)}" alt="${escapeText(item.name)}" />`
          : `<div class="caption-verify-thumb-missing">no image</div>`
      }
    </figure>
    <div class="caption-verify-name" title="${escapeText(item.name)}">${escapeText(item.name)}</div>
    <textarea class="nf-input caption-verify-text" data-caption
              spellcheck="false" title="Edit this caption"></textarea>
    <div class="caption-verify-actions">
      ${CAPTION_VERDICTS.map(
        (option) =>
          `<button type="button" class="nf-btn" data-decision="${escapeText(option.value)}">${escapeText(option.label)}</button>`,
      ).join("")}
    </div>
  `;
}
