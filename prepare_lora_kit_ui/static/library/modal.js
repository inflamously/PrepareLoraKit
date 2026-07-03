import { api } from "../core/api.js";
import { escapeText } from "../core/dom.js";
import { closeModal, showModal } from "../components/modal.js";

/**
 * Open the new/edit project modal. On a successful save, calls
 * `onSaved(card)` with the returned project card object.
 *
 * @param {{mode: "new" | "edit", project?: object, onSaved: (card: object) => void}} opts
 */
export async function openProjectModal({ mode, project = null, onSaved }) {
  const isEdit = mode === "edit";
  const networks = await loadNetworks();

  const modal = document.createElement("div");
  modal.className = "modal modal--compact";
  modal.innerHTML = `
    <div class="modal-header">
      <div>
        <h2>${isEdit ? "Edit project" : "New project"}</h2>
        <p>${isEdit ? "Update project metadata. Pipeline steps are preserved." : "Create a project from a dataset folder."}</p>
      </div>
    </div>
    <form class="lib-form" autocomplete="off">
      <label class="nf-field">
        <span class="nf-label">Name</span>
        <input id="projName" class="nf-input" type="text" placeholder="Defaults to the input folder name" />
      </label>

      <label class="nf-field">
        <span class="nf-label">Input folder</span>
        <div class="nf-inputgroup">
          <input id="projInput" class="nf-input" type="text" placeholder="/path/to/source/images" />
          <button type="button" id="browseInput" class="nf-btn nf-btn--secondary">Browse</button>
        </div>
      </label>

      <label class="nf-field">
        <span class="nf-label">Output folder</span>
        <div class="nf-inputgroup">
          <input id="projOutput" class="nf-input" type="text" placeholder="outputs/<dataset>" />
          <button type="button" id="browseOutput" class="nf-btn nf-btn--secondary">Browse</button>
        </div>
      </label>

      <label class="nf-field">
        <span class="nf-label">Network</span>
        <select id="projNetwork" class="nf-select">
          ${networks.map((n) => `<option value="${escapeText(n)}">${escapeText(n)}</option>`).join("")}
        </select>
      </label>

      <p id="projError" class="lib-form__error"></p>

      <div class="lib-form__actions">
        <button type="button" id="projCancel" class="nf-btn nf-btn--secondary">Cancel</button>
        <button type="submit" id="projSave" class="nf-btn nf-btn--primary">${isEdit ? "Save" : "Create"}</button>
      </div>
    </form>
  `;

  const nameEl = modal.querySelector("#projName");
  const inputEl = modal.querySelector("#projInput");
  const outputEl = modal.querySelector("#projOutput");
  const networkEl = modal.querySelector("#projNetwork");
  const errorEl = modal.querySelector("#projError");

  if (isEdit && project) {
    nameEl.value = project.name || "";
    inputEl.value = project.input_dir || "";
    outputEl.value = project.output_dir || "";
    if (project.network) networkEl.value = project.network;
  }

  // Track whether the user has customised name/output so we don't clobber them
  // when they pick an input folder.
  let outputCustomized = Boolean(outputEl.value.trim());
  let nameCustomized = Boolean(nameEl.value.trim());
  outputEl.addEventListener("input", () => {
    outputCustomized = Boolean(outputEl.value.trim());
  });
  nameEl.addEventListener("input", () => {
    nameCustomized = Boolean(nameEl.value.trim());
  });

  modal.querySelector("#browseInput").addEventListener("click", async () => {
    const result = await api().choose_folder();
    if (!result.path) return;
    inputEl.value = result.path;
    // Default the project name to the picked folder name (mirrors the CLI's
    // load_or_create_for_input behaviour) unless the user typed their own.
    if (!nameCustomized) {
      nameEl.value = folderName(result.path);
    }
    if (!outputCustomized) {
      const out = await api().default_output(result.path);
      outputEl.value = out.output_dir || "";
    }
  });

  modal.querySelector("#browseOutput").addEventListener("click", async () => {
    const result = await api().choose_folder();
    if (!result.path) return;
    outputEl.value = result.path;
    outputCustomized = true;
  });

  modal.querySelector("#projCancel").addEventListener("click", closeModal);

  modal.querySelector("form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      name: nameEl.value.trim(),
      input_dir: inputEl.value.trim(),
      output_dir: outputEl.value.trim(),
      network: networkEl.value,
    };
    if (!payload.name) {
      errorEl.textContent = "Name is required.";
      return;
    }

    const saveBtn = modal.querySelector("#projSave");
    saveBtn.disabled = true;
    errorEl.textContent = "";
    try {
      const result = isEdit
        ? await api().update_project(project.name, payload)
        : await api().create_project(payload);
      closeModal();
      await onSaved(result.project);
    } catch (err) {
      saveBtn.disabled = false;
      errorEl.textContent = cleanError(err);
    }
  });

  showModal(modal);
  nameEl.focus();
}

/**
 * Promise-based confirmation dialog rendered in the modal layer.
 *
 * @param {{title: string, message: string, confirmLabel?: string}} opts
 * @returns {Promise<boolean>}
 */
export function confirmModal({ title, message, confirmLabel = "Confirm" }) {
  return new Promise((resolve) => {
    const modal = document.createElement("div");
    modal.className = "modal modal--compact";
    modal.innerHTML = `
      <div class="modal-header">
        <div><h2>${escapeText(title)}</h2></div>
      </div>
      <div class="lib-form">
        <p>${escapeText(message)}</p>
        <div class="lib-form__actions">
          <button type="button" class="nf-btn nf-btn--secondary" data-act="cancel">Cancel</button>
          <button type="button" class="nf-btn nf-btn--primary danger" data-act="ok">${escapeText(confirmLabel)}</button>
        </div>
      </div>
    `;
    const finish = (value) => {
      closeModal();
      resolve(value);
    };
    modal.querySelector('[data-act="cancel"]').addEventListener("click", () => finish(false));
    modal.querySelector('[data-act="ok"]').addEventListener("click", () => finish(true));
    showModal(modal);
  });
}

async function loadNetworks() {
  try {
    const result = await api().list_networks();
    return result.networks && result.networks.length
      ? result.networks
      : ["flux-klein-9b"];
  } catch {
    return ["flux-klein-9b"];
  }
}

function folderName(path) {
  // Works for both POSIX and Windows paths; drops any trailing slash.
  const parts = String(path).replace(/[\\/]+$/, "").split(/[\\/]/);
  return parts[parts.length - 1] || "";
}

function cleanError(err) {
  const message = String(err && err.message ? err.message : err);
  // pywebview surfaces Python exceptions with a traceback-ish prefix; keep the
  // last meaningful line.
  const lines = message.split("\n").map((l) => l.trim()).filter(Boolean);
  return lines[lines.length - 1] || "Could not save project.";
}
