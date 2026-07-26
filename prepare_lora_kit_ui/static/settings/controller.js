/**
 * Wires the Settings buttons in both appbars.
 *
 * Settings is reachable from the library and from inside a project, so the same
 * handler binds two buttons. Missing elements are tolerated: the mock fixtures
 * build partial DOM, and a Settings button is never load-bearing for a run.
 */
import { openSettingsModal } from "./settings.js";

const BUTTON_IDS = ["openSettings", "openSettingsShell"];

export function bindSettingsEvents() {
  for (const id of BUTTON_IDS) {
    const button = document.getElementById(id);
    if (button) button.addEventListener("click", () => openSettingsModal());
  }
}
