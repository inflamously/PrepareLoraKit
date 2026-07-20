/**
 * Output-directory slice of the global {@link state} object.
 *
 * @typedef {Object} OutputState
 * @property {string} outputDir - Resolved output directory path; "" when unset.
 * @property {boolean} outputCustomized - True once the user overrides the default
 *   output path, so it is no longer auto-derived from {@link ProjectState.inputDir}.
 * @property {boolean} outputExists - True when {@link OutputState.outputDir} exists on
 *   disk. Reported by the backend on every project load; the path is resolved long
 *   before the folder is written, so the two are not interchangeable.
 */

/** @type {OutputState} */
export const outputState = {
  outputDir: "",
  outputCustomized: false,
  outputExists: false,
};
