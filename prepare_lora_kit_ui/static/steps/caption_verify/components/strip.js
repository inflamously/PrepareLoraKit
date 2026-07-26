import { escapeText } from "../../../core/dom.js";
import { reviewCard, syncReviewCards } from "../../../components/review_card.js";
import { CAPTION_VERDICTS, normalizeCaptionVerdict } from "../utils/verdicts.js";

// One filmstrip tile per image. Still a reviewCard — left-click selects,
// right-click cycles the verdict — but the tile only *shows* state now: the
// caption box and the verdict buttons live once, in the editor beside it.
export function captionVerifyTile(
  item,
  index,
  verdicts,
  { onSelect, onVerdictChange } = {},
) {
  const tile = reviewCard(item, verdicts, {
    className: "caption-verify-tile",
    title: `${item.name} — click to load; right-click to cycle verdict`,
    decisionOptions: CAPTION_VERDICTS,
    normalizeDecision: normalizeCaptionVerdict,
    renderBody: (entry) => renderTileBody(entry, index),
    onSelect,
    onDecisionChange: onVerdictChange,
  });
  if (!item.has_caption) {
    tile.classList.add("caption-verify-tile--nocaption");
  }
  return tile;
}

// `reviewed` and `isEdited` carry what the verdict classes cannot: every item
// starts on the "correct" default, so an unreviewed tile must not sit there
// wearing the same green dot as one the user actually judged.
export function syncCaptionVerifyTiles(
  tilesByPath,
  verdicts,
  { reviewed, isEdited } = {},
) {
  syncReviewCards(tilesByPath, verdicts, {
    decisionOptions: CAPTION_VERDICTS,
    normalizeDecision: normalizeCaptionVerdict,
  });
  tilesByPath.forEach((tile, path) => {
    tile.classList.toggle(
      "caption-verify-tile--reviewed",
      Boolean(reviewed?.has(path)),
    );
    tile.classList.toggle(
      "caption-verify-tile--edited",
      Boolean(isEdited?.(path)),
    );
  });
}

function renderTileBody(item, index) {
  const thumb = item.thumb_uri || item.uri;
  return `
    <span class="caption-verify-tile__frame">
      ${
        thumb
          ? `<img class="caption-verify-tile__img" loading="lazy" alt="" src="${escapeText(thumb)}" />`
          : `<span class="caption-verify-tile__missing">no image</span>`
      }
      <span class="caption-verify-tile__index">${escapeText(String(index + 1))}</span>
      <span class="caption-verify-tile__dot" aria-hidden="true"></span>
    </span>
    <span class="caption-verify-tile__name" title="${escapeText(item.name)}">${escapeText(item.name)}</span>
  `;
}
