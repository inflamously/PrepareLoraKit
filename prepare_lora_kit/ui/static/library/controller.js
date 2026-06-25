import { api } from "../core/api.js";
import { $, setText } from "../core/dom.js";
import { state } from "../+state/index.js";
import { loadProject } from "../project/controller.js";
import { renderLibrary } from "./view.js";
import { openProjectModal, confirmModal } from "./modal.js";

// ── view switching ──────────────────────────────────────────────────────────

export function showLibraryView() {
  $("shellView").classList.add("hidden");
  $("libraryView").classList.remove("hidden");
}

export function showShellView() {
  $("libraryView").classList.add("hidden");
  $("shellView").classList.remove("hidden");
}

// ── data ──────────────────────────────────────────────────────────────────

export async function loadLibrary() {
  const result = await api().list_projects();
  state.libraryProjects = result.projects || [];
  if (
    state.librarySelected &&
    !state.libraryProjects.some((p) => p.name === state.librarySelected)
  ) {
    state.librarySelected = null;
  }
  renderLibrary();
}

// ── selection / open ────────────────────────────────────────────────────────

export function selectLibraryProject(name) {
  state.librarySelected = name;
  renderLibrary();
}

export async function openProject(name) {
  const target = name || state.librarySelected;
  if (!target) return;

  const select = $("projectSelect");
  if (![...select.options].some((option) => option.value === target)) {
    select.append(new Option(target, target));
  }
  select.value = target;
  setText("shellProjectLabel", target);
  showShellView();
  await loadProject({ resetSession: true });
}

// ── CRUD actions (operate on the selected card) ───────────────────────────────

export function newProject() {
  openProjectModal({ mode: "new", onSaved: handleSaved });
}

export function editSelected() {
  if (!state.librarySelected) return;
  const project = state.libraryProjects.find(
    (p) => p.name === state.librarySelected,
  );
  if (!project) return;
  openProjectModal({ mode: "edit", project, onSaved: handleSaved });
}

export async function duplicateSelected() {
  if (!state.librarySelected) return;
  const result = await api().duplicate_project(state.librarySelected);
  await loadLibrary();
  if (result.project) {
    state.librarySelected = result.project.name;
    renderLibrary();
  }
}

export async function deleteSelected() {
  if (!state.librarySelected) return;
  const name = state.librarySelected;
  const ok = await confirmModal({
    title: "Delete project",
    message: `Delete "${name}"? This removes its config file. Output data is kept.`,
    confirmLabel: "Delete",
  });
  if (!ok) return;
  await api().delete_project(name);
  state.librarySelected = null;
  await loadLibrary();
}

async function handleSaved(card) {
  await loadLibrary();
  if (card && card.name) {
    state.librarySelected = card.name;
    renderLibrary();
  }
}

// ── events ──────────────────────────────────────────────────────────────────

export function bindLibraryEvents() {
  $("newProject").addEventListener("click", newProject);
  $("openProject").addEventListener("click", () => openProject());
  $("dupProject").addEventListener("click", duplicateSelected);
  $("editProject").addEventListener("click", editSelected);
  $("deleteProject").addEventListener("click", deleteSelected);
  $("backToLibrary").addEventListener("click", () => {
    showLibraryView();
    loadLibrary();
  });

  $("librarySearch").addEventListener("input", (event) => {
    state.libraryQuery = event.target.value;
    renderLibrary();
  });
  $("librarySort").addEventListener("change", (event) => {
    state.librarySort = event.target.value;
    renderLibrary();
  });
}
