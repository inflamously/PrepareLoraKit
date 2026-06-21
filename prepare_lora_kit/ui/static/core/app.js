import { api } from "./api.js";
import { setText } from "./dom.js";
import { bindEvents } from "../shell/events.js";
import { render } from "../shell/render.js";
import { loadProjects } from "../project/controller.js";

export async function init() {
  const info = await api().app_info();
  setText("rootLabel", info.project_root);
  await loadProjects();
  bindEvents();
  render();
}
