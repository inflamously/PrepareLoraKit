/**
 * Step/substep selection slice of the global {@link state} object. Keys are
 * `step.type` values from the loaded {@link import("../core/api.js").ProjectPayload}.
 *
 * @typedef {Object} StepState
 * @property {Set<string>} selectedSteps - `step.type` values currently enabled.
 * @property {Map<string, Set<string>>} selectedSubsteps - Per-step set of enabled
 *   substep ids; absence of an entry means "all substeps of that step".
 * @property {Set<string>} collapsedSteps - `step.type` values whose substep list
 *   is collapsed in the UI.
 */

/** @type {StepState} */
export const stepState = {
  selectedSteps: new Set(),
  selectedSubsteps: new Map(),
  collapsedSteps: new Set(),   // step.type values whose substep list is collapsed
};
