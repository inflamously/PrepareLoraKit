/**
 * Library (project grid) slice of the global {@link state} object.
 *
 * @typedef {Object} LibraryState
 * @property {import("../core/api.js").ProjectCard[]} libraryProjects - Detailed
 *   project card objects from `list_projects()`.
 * @property {string | null} librarySelected - Name of the currently selected card,
 *   or null.
 * @property {string} libraryQuery - Free-text search filter applied to the grid.
 * @property {"recent" | "name"} librarySort - Sort mode: "recent" (config mtime
 *   desc) or "name".
 */

/** @type {LibraryState} */
export const libraryState = {
  libraryProjects: [],
  librarySelected: null,
  libraryQuery: "",
  librarySort: "recent",
};
