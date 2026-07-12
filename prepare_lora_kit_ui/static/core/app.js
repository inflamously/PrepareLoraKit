import { api } from "./api.js";
import { setText } from "./dom.js";
import { bindEvents } from "../shell/events.js";
import { render } from "../shell/render.js";
import { applyBootstrap, loadProjects } from "../project/controller.js";
import {
  bindLibraryEvents,
  loadLibrary,
  showShellView,
} from "../library/controller.js";

export async function init() {
  const info = await api().app_info();
  setText("rootLabel", info.project_root);

  const projectList = await loadProjects();
  bindEvents();
  bindLibraryEvents();

  if (info.bootstrap) {
    // --mock launches straight into the shell for a specific project.
    await applyBootstrap(info.bootstrap);
    showShellView();
  } else {
    await loadLibrary(projectList);
    render();
  }
}
