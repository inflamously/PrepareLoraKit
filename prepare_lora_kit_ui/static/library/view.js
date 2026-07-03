import { $, setText, escapeText } from "../core/dom.js";
import { state } from "../+state/index.js";
import { newProject, openProject, selectLibraryProject } from "./controller.js";

const STATUS_PILL = {
  completed: "nf-pill--done",
  running: "nf-pill--running",
  failed: "nf-pill--danger",
  draft: "nf-pill--draft",
};

const FOOTER_BUTTONS = ["openProject", "dupProject", "editProject", "deleteProject"];

export function renderLibrary() {
  const grid = $("projectGrid");
  const all = state.libraryProjects || [];
  const query = (state.libraryQuery || "").trim().toLowerCase();

  const items = (query ? all.filter((p) => matches(p, query)) : all.slice());
  sortItems(items, state.librarySort);

  const cards = items.map(buildCard);
  if (query && items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "lib-empty";
    empty.textContent = `No projects match "${state.libraryQuery.trim()}".`;
    cards.push(empty);
  }
  cards.push(buildNewCard());
  grid.replaceChildren(...cards);

  // Footer summary + action availability.
  setText("libraryCount", `${all.length} project${all.length === 1 ? "" : "s"}`);
  const selected = Boolean(state.librarySelected);
  for (const id of FOOTER_BUTTONS) {
    $(id).disabled = !selected;
  }
  setText(
    "libraryHint",
    selected ? state.librarySelected : "Select a project to open",
  );
}

function matches(project, query) {
  return [project.name, project.network, project.token, project.input_dir]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(query));
}

function sortItems(items, sort) {
  if (sort === "name") {
    items.sort((a, b) => a.name.localeCompare(b.name));
  } else {
    // "recent" — most-recently-modified config first.
    items.sort((a, b) => (b.mtime || 0) - (a.mtime || 0));
  }
}

function buildCard(project) {
  const card = document.createElement("button");
  card.type = "button";
  card.className = "nf-projcard";
  if (project.name === state.librarySelected) {
    card.classList.add("is-selected");
  }

  const pill = STATUS_PILL[project.status] || STATUS_PILL.draft;
  const status = project.status || "draft";
  const meta =
    [project.network, project.token].filter(Boolean).join(" · ") || "not set";

  card.innerHTML = `
    <div class="nf-projcard__cover">
      <span class="nf-projcard__mono">${escapeText(project.initials || "??")}</span>
      <span class="nf-projcard__badge">
        <span class="nf-pill ${pill}"><span class="nf-pill__dot"></span>${escapeText(status)}</span>
      </span>
    </div>
    <div class="nf-projcard__body">
      <div class="nf-projcard__name">${escapeText(project.name)}</div>
      <div class="nf-projcard__meta">${escapeText(meta)}</div>
    </div>
  `;

  card.addEventListener("click", () => selectLibraryProject(project.name));
  card.addEventListener("dblclick", () => openProject(project.name));
  return card;
}

function buildNewCard() {
  const card = document.createElement("button");
  card.type = "button";
  card.className = "nf-projcard nf-projcard--new";
  card.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <line x1="12" y1="5" x2="12" y2="19"></line>
      <line x1="5" y1="12" x2="19" y2="12"></line>
    </svg>
    <span>New project</span>
  `;
  card.addEventListener("click", () => newProject());
  return card;
}
