import { escapeText } from "../../core/dom.js";
import { normalizeDecision, optionForDecision } from "./decisions.js";
import { formatQuality, formatScoreValue } from "./format.js";

export function renderSourceReviewDetail(detail, item, decision) {
  if (!item) {
    detail.innerHTML = `
      <div class="source-review-empty">
        <strong>No images to review</strong>
        <span>The quality gate did not return review items.</span>
      </div>
    `;
    return;
  }

  const scores = Object.entries(item.scores || {});
  const autoReasons = item.auto_reasons || [];
  const normalized = normalizeDecision(decision);
  const decisionLabel = optionForDecision(normalized).label;

  detail.innerHTML = `
    <div class="source-review-preview">
      <img src="${escapeText(item.uri)}" alt="${escapeText(item.name)}" />
    </div>
    <div class="source-review-detail-body">
      <div class="source-review-detail-header">
        <div>
          <strong title="${escapeText(item.name)}">${escapeText(item.name)}</strong>
          <small title="${escapeText(item.path)}">${escapeText(item.path)}</small>
        </div>
        <span class="review-decision-pill ${escapeText(normalized)}">
          ${escapeText(decisionLabel)}
        </span>
      </div>
      <div class="quality-summary">
        <div>
          <span>Quality</span>
          <strong>${escapeText(formatQuality(item.quality))}</strong>
        </div>
        <div>
          <span>Auto gate</span>
          <strong>${item.auto_reject ? "Rejected" : "Passed"}</strong>
        </div>
      </div>
      <section class="quality-section">
        <h3>Gate Results</h3>
        ${renderScoreRows(scores)}
      </section>
      <section class="quality-section">
        <h3>Gate Findings</h3>
        ${renderAutoReasons(autoReasons)}
      </section>
    </div>
  `;
}

function renderScoreRows(scores) {
  if (scores.length === 0) {
    return `<p class="quality-empty">No score output available.</p>`;
  }
  return `
    <dl class="quality-score-list">
      ${scores
        .map(
          ([name, value]) => `
            <div>
              <dt>${escapeText(name)}</dt>
              <dd>${escapeText(formatScoreValue(value))}</dd>
            </div>
          `,
        )
        .join("")}
    </dl>
  `;
}

function renderAutoReasons(reasons) {
  if (reasons.length === 0) {
    return `<p class="quality-empty">No automatic gate failures.</p>`;
  }
  return `
    <ul class="quality-reason-list">
      ${reasons.map((reason) => `<li>${escapeText(reason)}</li>`).join("")}
    </ul>
  `;
}
