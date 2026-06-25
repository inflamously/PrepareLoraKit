import { jobState } from "./jobs.js";
import { libraryState } from "./library.js";
import { mockRuntimeState } from "./mock_runtime.js";
import { outputState } from "./outputs.js";
import { projectState } from "./projects.js";
import { stepState } from "./steps.js";

export const state = {
  ...projectState,
  ...stepState,
  ...jobState,
  ...outputState,
  ...mockRuntimeState,
  ...libraryState,
};
