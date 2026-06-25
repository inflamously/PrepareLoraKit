import { $ } from "../core/dom.js";
import { state } from "../+state/index.js";
import { reloadCurrentProject, selectPending } from "../project/controller.js";
import { cancelRun, openOutput, startRun } from "../job/controller.js";
import { setActiveTab } from "./tabs.js";

export function bindEvents() {
  $("tabPipeline").addEventListener("click", () => setActiveTab("pipeline"));
  $("tabMetadata").addEventListener("click", () => setActiveTab("metadata"));
  $("tokenInput").addEventListener("input", (event) => {
    state.token = event.target.value;
  });
  $("refreshProject").addEventListener("click", () =>
    reloadCurrentProject({ preserveSelection: true }),
  );
  $("selectPending").addEventListener("click", selectPending);
  $("runButton").addEventListener("click", startRun);
  $("cancelButton").addEventListener("click", cancelRun);
  $("openOutput").addEventListener("click", openOutput);
}
