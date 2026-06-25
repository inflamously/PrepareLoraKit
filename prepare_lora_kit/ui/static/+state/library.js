export const libraryState = {
  /** Detailed project card objects from list_projects(). */
  libraryProjects: [],
  /** Name of the currently selected card, or null. */
  librarySelected: null,
  /** Free-text search filter applied to the grid. */
  libraryQuery: "",
  /** Sort mode: "recent" (config mtime desc) or "name". */
  librarySort: "recent",
};
