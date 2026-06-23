import { state } from "../+state/index.js";

export function selectedStepArray() {
  if (!state.project) return [];

  return state.project.steps
    .map((step) => step.type)
    .filter((type) => state.selectedSteps.has(type));
}
