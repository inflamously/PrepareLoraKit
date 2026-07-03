import { jobState } from "./jobs.js";
import { libraryState } from "./library.js";
import { mockRuntimeState } from "./mock_runtime.js";
import { outputState } from "./outputs.js";
import { projectState } from "./projects.js";
import { stepState } from "./steps.js";

/**
 * Global, mutable UI state shared across controllers and views. It is the merge
 * of the per-domain slices defined in this folder; mutate it in place (the same
 * object reference is imported everywhere via `core/state.js`).
 *
 * @typedef {ProjectState & StepState & JobState & OutputState &
 *   MockRuntimeState & LibraryState} AppState
 */

/** @type {AppState} */
export const state = {
  ...projectState,
  ...stepState,
  ...jobState,
  ...outputState,
  ...mockRuntimeState,
  ...libraryState,
};
