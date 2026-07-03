import { $ } from "../core/dom.js";
import { state } from "../+state/index.js";
import {
  collapseAll,
  expandAll,
  reloadCurrentProject,
  selectPending,
  unselectAll,
} from "../project/controller.js";
import { cancelRun, openInput, openOutput, startRun } from "../job/controller.js";
import { scrollLogsToBottom } from "../job/view.js";
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
  $("collapseAllSteps").addEventListener("click", collapseAll);
  $("expandAllSteps").addEventListener("click", expandAll);
  $("unselectAllSteps").addEventListener("click", unselectAll);
  $("selectPending").addEventListener("click", selectPending);
  $("runButton").addEventListener("click", startRun);
  $("cancelButton").addEventListener("click", cancelRun);
  $("openOutput").addEventListener("click", openOutput);
  $("openInput").addEventListener("click", openInput);
  $("autoScroll").addEventListener("change", () => scrollLogsToBottom());
}
