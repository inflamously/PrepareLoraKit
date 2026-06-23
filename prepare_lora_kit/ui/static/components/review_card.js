export function reviewCard(
  item,
  decisions,
  {
    className,
    title,
    decisionOptions,
    normalizeDecision,
    renderBody,
    onSelect,
    onDecisionChange,
  } = {},
) {
  const card = document.createElement("div");
  card.className = className;
  if (title) {
    card.title = title;
  }
  card.innerHTML = renderBody(item);

  const setDecision = (decision, { notify = true } = {}) => {
    const normalized = normalizeDecision(decision);

    decisions[item.path] = normalized;
    updateReviewCardDecision(card, normalized, decisionOptions);
    if (notify) {
      onDecisionChange?.(item);
    }
  };

  const cycleDecision = () => {
    const current = normalizeDecision(decisions[item.path]);
    const index = decisionOptions.findIndex(
      (option) => option.value === current,
    );
    const nextIndex = (index + 1) % decisionOptions.length;
    setDecision(decisionOptions[nextIndex].value);
  };

  card.querySelectorAll("[data-decision]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      setDecision(button.dataset.decision);
    });
  });

  card.addEventListener("click", (event) => {
    if (
      event.target instanceof Element &&
      event.target.closest("[data-decision]")
    ) {
      return;
    }
    onSelect?.(item);
  });

  card.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    cycleDecision();
  });

  setDecision(decisions[item.path], { notify: false });
  return card;
}

export function syncReviewCards(cardsByPath, decisions, config) {
  cardsByPath.forEach((card, path) => {
    updateReviewCardDecision(
      card,
      config.normalizeDecision(decisions[path]),
      config.decisionOptions,
    );
  });
}

function updateReviewCardDecision(card, decision, decisionOptions) {
  const values = decisionOptions.map((entry) => entry.value);
  card.classList.remove(...values);
  card.classList.add(decision);
  card.querySelectorAll("[data-decision]").forEach((button) => {
    button.setAttribute(
      "aria-pressed",
      String(button.dataset.decision === decision),
    );
  });
}
