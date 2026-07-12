/**
 * Start the application once the pywebview API is available.
 *
 * pywebview readiness is a one-shot event. Checking the API immediately as well
 * as listening for the event covers both possible module/injection orderings.
 */
export function bootOnPywebviewReady(start, target = globalThis) {
  let started = false;

  const boot = () => {
    if (started || !target.pywebview?.api) return false;
    started = true;
    start();
    return true;
  };

  target.addEventListener("pywebviewready", boot, { once: true });
  boot();
  return boot;
}
