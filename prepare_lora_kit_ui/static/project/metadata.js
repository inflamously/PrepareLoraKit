import { $ } from "../core/dom.js";
import { state } from "../+state/index.js";

const EMPTY = "none";

// Name/network/folders are read-only here (edited through the Library modal);
// the concept token stays editable and is mirrored from state.token.
export function renderMetadata() {
  const project = state.project;

  setMeta("metaName", project?.name);
  setMeta("metaNetwork", networkLabel(project));
  setMeta("metaInput", state.inputDir || project?.input_dir);
  setMeta("metaOutput", state.outputDir);
  syncToken();
}

function syncToken() {
  const el = $("tokenInput");
  // Don't clobber the field (or move the caret) while the user is typing.
  if (!el || el === document.activeElement) return;
  el.value = state.token || "";
}

function networkLabel(project) {
  if (!project) return "";
  return project.network_type
    ? `${project.network} / ${project.network_type}`
    : project.network;
}

function setMeta(id, value) {
  const el = $(id);
  if (!el) return;
  const text = (value || "").toString().trim();
  el.textContent = text || EMPTY;
  el.classList.toggle("is-empty", !text);
}
