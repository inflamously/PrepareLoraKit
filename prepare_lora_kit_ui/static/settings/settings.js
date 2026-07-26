/**
 * Settings modal: machine-wide options shared by every project.
 *
 * Opened from a button, never from the pipeline — it must stay out of
 * job/controller.js `handlePendingInput`, and it must not use
 * `modalCancelButton`, which cancels a *run*.
 *
 * The modal opens on `get_settings` alone, which is pure disk plus torch-free
 * catalogs. Anything slower — the Hub, a VRAM probe — is behind its own button
 * so opening Settings can never stall on the network or a torch import.
 */
import { api } from "../core/api.js";
import { escapeText } from "../core/dom.js";
import { cleanError } from "../core/errors.js";
import { closeModal, showModal } from "../components/modal.js";
import { applySettings, buildSettingsModal, collectSettings } from "./form.js";

/** Open the Settings modal. Resolves once it is on screen. */
export async function openSettingsModal() {
  const payload = await api().get_settings();
  const modal = buildSettingsModal(payload);
  applySettings(modal, payload.settings);

  const errorEl = modal.querySelector("#settingsError");
  const saveBtn = modal.querySelector("#settingsSave");
  const setError = (message) => {
    errorEl.textContent = message || "";
  };

  modal.querySelector("#settingsCancel").addEventListener("click", closeModal);

  for (const button of modal.querySelectorAll("[data-browse]")) {
    button.addEventListener("click", async () => {
      const result = await api().choose_folder();
      if (!result || !result.path) return;
      modal.querySelector(`[data-setting="${button.dataset.browse}"]`).value = result.path;
    });
  }

  modal.querySelector("#settingsCopyLogin").addEventListener("click", () => {
    const input = modal.querySelector("#settingsLoginCommand");
    input.select();
    // execCommand is deprecated on the web but is the only copy path that works
    // in every pywebview backend; navigator.clipboard is absent in some of them.
    try {
      document.execCommand("copy");
    } catch {
      /* selection alone still lets the user copy manually */
    }
  });

  wireHfCheck(modal, setError);
  wireModelCheck(modal, setError);
  wireDetect(modal, setError);

  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    setError("");
    try {
      await api().save_settings(collectSettings(modal));
      closeModal();
    } catch (err) {
      saveBtn.disabled = false;
      setError(cleanError(err, "Could not save settings."));
    }
  });

  showModal(modal);
  return modal;
}

function wireHfCheck(modal, setError) {
  const button = modal.querySelector("#settingsHfCheck");
  const status = modal.querySelector("#settingsHfStatus");
  button.addEventListener("click", async () => {
    button.disabled = true;
    status.textContent = "Checking…";
    try {
      const result = await api().hf_status();
      status.textContent = describeHfStatus(result);
      status.dataset.state = result.account && result.account.ok ? "ok" : "warn";
    } catch (err) {
      status.textContent = "Check failed.";
      status.dataset.state = "warn";
      setError(cleanError(err, "Could not check the Hugging Face login."));
    } finally {
      button.disabled = false;
    }
  });
}

function describeHfStatus(result) {
  const account = result.account || {};
  if (account.ok) {
    return `Signed in as ${account.name || "unknown user"}.`;
  }
  const token = result.token || {};
  if (!token.present) {
    return `No token found. Run \`${result.login_command}\`.`;
  }
  return `Token found but unusable: ${account.error || "unknown error"}`;
}

function wireModelCheck(modal, setError) {
  const button = modal.querySelector("#settingsCheckModels");
  const list = modal.querySelector("#settingsAccessResults");
  button.addEventListener("click", async () => {
    button.disabled = true;
    list.replaceChildren();
    list.textContent = "Checking…";
    try {
      // Check what is on screen right now, not what was last saved — otherwise
      // trying out a model id means saving first.
      const payload = collectSettings(modal);
      const { results } = await api().check_model_access(idsToCheck(payload));
      renderAccessResults(list, results);
    } catch (err) {
      list.textContent = "";
      setError(cleanError(err, "Could not check model access."));
    } finally {
      button.disabled = false;
    }
  });
}

function idsToCheck(payload) {
  const defaults = payload.project_defaults || {};
  return [
    defaults.caption_model_id,
    defaults.t2i_model_id,
    defaults.vae_model_id,
    defaults.coverage_embedding_model,
  ].filter((value) => value && value !== "auto" && !/^[.~/]/.test(value) && !value.includes("::"));
}

function renderAccessResults(list, results) {
  list.textContent = "";
  if (!results || !results.length) {
    list.textContent = "No Hub model ids configured — nothing to check.";
    return;
  }
  list.innerHTML = results
    .map(
      (result) => `
        <li class="settings-access__item" data-state="${escapeText(result.status)}">
          <span class="settings-access__id">${escapeText(result.repo_id)}</span>
          <span class="settings-access__msg">${escapeText(result.message)}</span>
        </li>`,
    )
    .join("");
}

function wireDetect(modal, setError) {
  const button = modal.querySelector("#settingsDetect");
  const label = modal.querySelector("#settingsDetected");
  button.addEventListener("click", async () => {
    button.disabled = true;
    label.textContent = "Detecting…";
    try {
      const info = await api().detect_hardware();
      if (!info.cuda) {
        label.textContent = "No CUDA GPU detected.";
        return;
      }
      label.textContent = `${info.total_vram_gb} GB detected.`;
      if (info.suggested_tier) {
        modal.querySelector('[data-setting="vram_tier"]').value = info.suggested_tier;
      }
    } catch (err) {
      label.textContent = "";
      setError(cleanError(err, "Could not detect hardware."));
    } finally {
      button.disabled = false;
    }
  });
}
