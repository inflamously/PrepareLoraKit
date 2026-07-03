/**
 * Global error surface.
 *
 * The app runs inside a pywebview window with no visible console unless launched
 * with `--debug`, and the entry point (`init`) is an async event listener whose
 * rejections are otherwise swallowed. Without this, any uncaught error leaves the
 * UI silently half-initialised with no trace. This installs catch-all handlers
 * that log to the console AND paint a visible banner, so failures are never silent.
 */

let bannerEl = null;

function showBanner(title, detail) {
  if (!bannerEl) {
    bannerEl = document.createElement("div");
    bannerEl.id = "globalError";
    bannerEl.setAttribute("role", "alert");
    bannerEl.style.cssText = [
      "position:fixed", "top:0", "left:0", "right:0", "z-index:9999",
      "background:#7f1d1d", "color:#fff", "font:12px/1.5 monospace",
      "padding:8px 12px", "white-space:pre-wrap", "max-height:40vh",
      "overflow:auto", "box-shadow:0 2px 8px rgba(0,0,0,.4)",
    ].join(";");
    bannerEl.addEventListener("click", () => bannerEl.remove());
    document.body.appendChild(bannerEl);
  }
  bannerEl.textContent = `⚠ ${title}\n${detail}\n(click to dismiss)`;
}

function describe(value) {
  if (value instanceof Error) return `${value.name}: ${value.message}\n${value.stack || ""}`;
  return String(value);
}

/** Install global handlers. Call once, as early as possible during boot. */
export function installErrorSurface() {
  globalThis.addEventListener("error", (event) => {
    console.error("Uncaught error:", event.error || event.message);
    showBanner("Uncaught error", describe(event.error || event.message));
  });

  globalThis.addEventListener("unhandledrejection", (event) => {
    console.error("Unhandled promise rejection:", event.reason);
    showBanner("Unhandled promise rejection", describe(event.reason));
  });
}

/**
 * Run an async boot function, surfacing any rejection instead of swallowing it.
 * @param {() => Promise<void>} fn
 */
export function runBoot(fn) {
  Promise.resolve()
    .then(fn)
    .catch((err) => {
      console.error("Boot failed:", err);
      showBanner("Boot failed — the UI did not finish loading", describe(err));
    });
}
