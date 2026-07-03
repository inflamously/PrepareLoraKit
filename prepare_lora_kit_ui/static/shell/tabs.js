// Switch the workspace panel between the "pipeline" and "metadata" tabs.
export function setActiveTab(name) {
  for (const tab of document.querySelectorAll(".nf-tab")) {
    const active = tab.dataset.tab === name;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
  }
  for (const pane of document.querySelectorAll(".tab-pane")) {
    pane.classList.toggle("is-hidden", pane.dataset.pane !== name);
  }
}
