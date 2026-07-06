/**
 * Project-selection slice of the global {@link state} object.
 *
 * @typedef {Object} ProjectState
 * @property {string[]} projects - Names of all known projects (the shell only
 *   needs names; full card objects live in {@link LibraryState.libraryProjects}).
 * @property {import("../core/api.js").ProjectPayload | null} project - The
 *   currently loaded project (steps, config, etc.), or null when none is open.
 * @property {string} activeProject - Name of the active project; "" when none.
 * @property {string} inputDir - Selected source dataset directory; "" when unset.
 * @property {string} token - Concept/trigger token, mirrored into the metadata UI.
 */

/** @type {ProjectState} */
export const projectState = {
  projects: [],
  project: null,
  activeProject: "",
  inputDir: "",
  token: "",
};
