import { state } from "../+state/index.js";

export function selectedStepArray() {
  if (!state.project) return [];

  return state.project.steps
    .map((step) => step.type)
    .filter((type) => state.selectedSteps.has(type));
}

export function selectedSubstepMap() {
  if (!state.project) return {};

  const selected = {};
  for (const step of state.project.steps) {
    if (!state.selectedSteps.has(step.type)) continue;
    const explicit = state.selectedSubsteps.get(step.type);
    const substeps = step.substeps || [];
    const enabled = substeps
      .map((substep) => substep.id)
      .filter((id) => explicit ? explicit.has(id) : substeps.find((substep) => substep.id === id)?.enabled !== false);
    selected[step.type] = enabled;
  }
  return selected;
}
