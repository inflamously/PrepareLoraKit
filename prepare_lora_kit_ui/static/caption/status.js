// One line any model-backed step can show about its runtime, plus elapsed time and
// progress for a long load. Every field past `phase` and `message` is optional.
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
  const weights = weightsLine(status);
  if (weights) nodes.push(line("caption-status__weights", weights));
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

// How much of the checkpoint is in, for the minutes a big one spends landing.
// The detail line below counts whatever unit the current tqdm bar happens to
// use — shards of an unnamed component — so this is the only line that says how
// far through the *load* it is.
//
// Skipped rather than zeroed when the step publishes nothing: "0.0 / 0.0 GB"
// reads as a checkpoint with no weights in it. The step omits both fields
// whenever it cannot measure the files, which includes the whole first-run
// download, when nothing is loaded because nothing has arrived yet.
function weightsLine(status) {
  const loaded = Number(status.weights_loaded_bytes);
  const total = Number(status.weights_total_bytes);
  if (!Number.isFinite(loaded) || !Number.isFinite(total) || total <= 0) return "";
  const done = Math.min(Math.max(loaded, 0), total);
  const percent = Math.round((done / total) * 100);
  return `Weights ${formatSizePair(done, total)} · ${percent}%`;
}

// "6.2 / 9.4 GB" — both figures in the total's unit, so the pair reads as one
// measurement rather than two. Mirrors load_status._bytes on the Python side,
// which formats the download line the same way.
const SIZE_UNITS = ["B", "KB", "MB", "GB", "TB"];

function formatSizePair(loaded, total) {
  let step = 0;
  while (total >= 1024 ** (step + 1) && step < SIZE_UNITS.length - 1) step += 1;
  const scale = 1024 ** step;
  const digits = step <= 1 ? 0 : 1;
  return `${(loaded / scale).toFixed(digits)} / ${(total / scale).toFixed(digits)} ${SIZE_UNITS[step]}`;
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
