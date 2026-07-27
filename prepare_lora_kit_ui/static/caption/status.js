// One line any model-backed step can show about its runtime, plus the two
// things a long load needs on top of it: how long it has been going, and how
// far it has got. A 9B FLUX.2 klein takes minutes to load and reports nothing
// on its own — without an elapsed count and a bar, "loading" and "hung" are the
// same screen.
//
// Every field past `phase` and `message` is optional, so a step that only
// publishes those two renders exactly as it did before.
export function renderCaptionStatus(element, status) {
  if (!element) return;
  if (!status || !status.phase) {
    element.classList.add("hidden");
    element.replaceChildren();
    return;
  }

  const parts = [status.message || status.phase];
  const meta = [status.adapter, status.device, status.quantization]
    .filter(Boolean)
    .join(" / ");
  if (meta) parts.push(meta);
  const elapsed = formatElapsed(status.elapsed_s);
  if (elapsed) parts.push(elapsed);

  const nodes = [line("caption-status__line", parts.join(" - "))];
  if (status.detail) nodes.push(line("caption-status__detail", status.detail));
  const bar = progressBar(status.progress);
  if (bar) nodes.push(bar);

  element.replaceChildren(...nodes);
  element.dataset.phase = status.phase;
  element.classList.remove("hidden");
}

/** `48s` / `10m 12s` — matches load_status.format_elapsed on the Python side. */
export function formatElapsed(seconds) {
  if (typeof seconds !== "number" || !Number.isFinite(seconds)) return "";
  const total = Math.max(0, Math.floor(seconds));
  if (total < 60) return `${total}s`;
  return `${Math.floor(total / 60)}m ${String(total % 60).padStart(2, "0")}s`;
}

function line(className, text) {
  const element = document.createElement("div");
  element.className = className;
  element.textContent = text;
  return element;
}

// Only drawn for a real fraction: a bar stuck at 0% because the step sent null
// reads as "no progress made", which is a worse lie than no bar at all.
function progressBar(fraction) {
  if (typeof fraction !== "number" || !Number.isFinite(fraction)) return null;
  const clamped = Math.min(1, Math.max(0, fraction));
  const bar = document.createElement("div");
  bar.className = "caption-status__bar";
  bar.setAttribute("role", "progressbar");
  bar.setAttribute("aria-valuemin", "0");
  bar.setAttribute("aria-valuemax", "100");
  bar.setAttribute("aria-valuenow", String(Math.round(clamped * 100)));

  const fill = document.createElement("span");
  fill.className = "caption-status__fill";
  fill.style.width = `${(clamped * 100).toFixed(1)}%`;
  bar.append(fill);
  return bar;
}
