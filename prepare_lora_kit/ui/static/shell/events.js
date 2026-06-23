import { api } from "../core/api.js";
import { $ } from "../core/dom.js";
import { state } from "../+state/index.js";
import { syncCaptionModelInput } from "../caption/config.js";
import {
  loadProject,
  loadProjectForInput,
  reloadCurrentProject,
  selectPending,
} from "../project/controller.js";
import { cancelRun, openOutput, startRun } from "../job/controller.js";

export function bindEvents() {
  $("chooseInput").addEventListener("click", async () => {
    const result = await api().choose_folder();
    if (!result.path) return;

    $("inputDir").value = result.path;
    await loadProjectForInput();
  });

  $("chooseOutput").addEventListener("click", async () => {
    const result = await api().choose_folder();
    if (!result.path) return;

    $("outputDir").value = result.path;
    state.outputDir = result.path;
    state.outputCustomized = true;
    await reloadCurrentProject();
  });

  $("inputDir").addEventListener("change", loadProjectForInput);
  $("outputDir").addEventListener("change", async () => {
    state.outputDir = $("outputDir").value;
    state.outputCustomized = Boolean(state.outputDir.trim());
    await reloadCurrentProject();
  });

  $("projectSelect").addEventListener("change", () =>
    loadProject({ resetSession: true }),
  );
  $("captionModelPreset").addEventListener("change", syncCaptionModelInput);
  $("refreshProject").addEventListener("click", () =>
    reloadCurrentProject({ preserveSelection: true }),
  );
  $("selectPending").addEventListener("click", selectPending);
  $("runButton").addEventListener("click", startRun);
  $("cancelButton").addEventListener("click", cancelRun);
  $("openOutput").addEventListener("click", openOutput);
}
