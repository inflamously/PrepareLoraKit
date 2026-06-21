import { renderJob } from "../job/view.js";
import { renderSteps } from "../project/view.js";

export function render() {
  renderSteps();
  renderJob();
}
