/**
 * Output-directory slice of the global {@link state} object.
 *
 * @typedef {Object} OutputState
 * @property {string} outputDir - Resolved output directory path; "" when unset.
 * @property {boolean} outputCustomized - True once the user overrides the default
 *   output path, so it is no longer auto-derived from {@link ProjectState.inputDir}.
 */

/** @type {OutputState} */
export const outputState = {
  outputDir: "",
  outputCustomized: false,
};
