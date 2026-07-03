/**
 * Mock-runtime slice of the global {@link state} object. Drives the dev/test
 * runtime that simulates a run instead of executing the real pipeline.
 *
 * @typedef {Object} MockRuntimeState
 * @property {boolean} mockRuntime - True when the active project runs against the
 *   mock runtime (i.e. `activeProject === mockProjectName`).
 * @property {string | null} mockProjectName - Name of the project flagged for mock
 *   execution by the bootstrap payload, or null.
 * @property {"auto" | string} mockCurateCoverage - Coverage mode the mock curate
 *   step reports; defaults to "auto".
 */

/** @type {MockRuntimeState} */
export const mockRuntimeState = {
  mockRuntime: false,
  mockProjectName: null,
  mockCurateCoverage: "auto",
};
