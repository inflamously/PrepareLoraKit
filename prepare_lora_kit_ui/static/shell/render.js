import { renderJob } from "../job/view.js";
import { renderMetadata } from "../project/metadata.js";
import { renderSteps } from "../project/view.js";

export function render() {
  renderMetadata();
  renderSteps();
  renderJob();
}
