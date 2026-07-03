export function renderCaptionStatus(element, status) {
  if (!element) return;
  if (!status || !status.phase) {
    element.classList.add("hidden");
    element.textContent = "";
    return;
  }

  const parts = [status.message || status.phase];
  const meta = [status.adapter, status.device, status.quantization]
    .filter(Boolean)
    .join(" / ");
  if (meta) parts.push(meta);
  element.textContent = parts.join(" - ");
  element.dataset.phase = status.phase;
  element.classList.remove("hidden");
}
