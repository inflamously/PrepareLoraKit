/**
 * The Settings modal's markup and value marshalling.
 *
 * Kept apart from settings.js so the controller stays about behaviour (loading,
 * saving, the Hub buttons) and this file stays about shape.
 */
import { escapeText } from "../core/dom.js";
import { modelField, selectField, textField } from "./fields.js";

/** Build the modal element for a `get_settings` payload. */
export function buildSettingsModal(payload) {
  const { choices, placeholders, settings_path: path, login_command: loginCommand } = payload;
  const modal = document.createElement("div");
  modal.className = "modal settings-modal";
  modal.innerHTML = `
    <div class="modal-header">
      <div>
        <h2>Settings</h2>
        <p>Machine-wide options shared by every project.</p>
      </div>
    </div>

    <div class="settings-body">
      <section class="settings-section">
        <h3>Hugging Face</h3>
        <p class="settings-note">
          PrepareLoraKit never stores a token. It reuses the one the Hugging Face CLI
          saves, so sign in once in a terminal and every project picks it up.
        </p>
        <div class="settings-row">
          <span class="nf-label">Status</span>
          <span id="settingsHfStatus" class="settings-status">Not checked yet.</span>
          <button type="button" id="settingsHfCheck" class="nf-btn nf-btn--secondary nf-btn--sm">
            Check login
          </button>
        </div>
        <div class="nf-field settings-field">
          <span class="nf-label">Sign in with</span>
          <div class="nf-inputgroup">
            <input id="settingsLoginCommand" class="nf-input" type="text" readonly />
            <button type="button" id="settingsCopyLogin" class="nf-btn nf-btn--secondary">Copy</button>
          </div>
          <span class="settings-help">Run this in a terminal, then press Check login.</span>
        </div>
        ${textField("hf_home", "Model cache folder", placeholders.hf_home, {
          browse: true,
          help: "Where Hugging Face downloads models. Takes effect after restarting the app.",
        })}
        <div class="settings-row">
          <button type="button" id="settingsCheckModels" class="nf-btn nf-btn--secondary nf-btn--sm">
            Check model access
          </button>
          <span class="settings-help">
            Asks the Hub whether this machine can read the models configured below.
          </span>
        </div>
        <ul id="settingsAccessResults" class="settings-access"></ul>
      </section>

      <section class="settings-section">
        <h3>Hardware</h3>
        <div class="settings-row">
          ${selectField("vram_tier", "VRAM tier", choices.vram_tier, placeholders.vram_tier)}
          <button type="button" id="settingsDetect" class="nf-btn nf-btn--secondary nf-btn--sm">
            Detect
          </button>
          <span id="settingsDetected" class="settings-status"></span>
        </div>
        ${textField("cuda_device", "CUDA device", placeholders.cuda_device, {
          help: "Comma-separated GPU indices for SeedVR2. Leave empty for the first GPU.",
        })}
        ${textField("seedvr2_submodule_dir", "SeedVR2 folder", placeholders.seedvr2_submodule_dir, {
          browse: true,
        })}
        ${textField("seedvr2_model_dir", "SeedVR2 checkpoints", placeholders.seedvr2_model_dir, {
          browse: true,
        })}
      </section>

      <section class="settings-section">
        <h3>Defaults for new projects</h3>
        <p class="settings-note">
          Copied into a project's config when it is created. Existing projects keep
          whatever their own config already says.
        </p>
        ${modelField("caption_model_id", "Caption model", choices.caption_model_id,
                     placeholders.caption_model_id,
                     "The one field a run cannot start without.")}
        ${selectField("caption_model_task", "Caption task", choices.caption_model_task,
                      placeholders.caption_model_task)}
        ${modelField("t2i_model_id", "Caption verifier model", choices.t2i_model_id,
                     placeholders.t2i_model_id)}
        ${modelField("vae_model_id", "VAE model", [], placeholders.vae_model_id)}
        ${modelField("coverage_embedding_model", "Coverage embedding model",
                     choices.coverage_embedding_model, placeholders.coverage_embedding_model)}
        ${modelField("seedvr2_dit_model", "SeedVR2 checkpoint", choices.seedvr2_dit_model,
                     placeholders.seedvr2_dit_model)}
        ${selectField("caption_model_type", "Caption length tokenizer", choices.caption_model_type,
                      placeholders.caption_model_type)}
      </section>
    </div>

    <p id="settingsError" class="settings-error"></p>

    <div class="settings-actions">
      <span class="settings-path" title="${escapeText(path)}">${escapeText(path)}</span>
      <button type="button" id="settingsCancel" class="nf-btn nf-btn--secondary">Close</button>
      <button type="button" id="settingsSave" class="nf-btn nf-btn--primary">Save</button>
    </div>
  `;

  // Assigned rather than interpolated: the command is server-supplied text and
  // an input's value is not a place markup escaping can be reasoned about.
  modal.querySelector("#settingsLoginCommand").value = loginCommand || "";
  return modal;
}

const GROUPS = {
  huggingface: ["hf_home"],
  hardware: ["vram_tier", "cuda_device", "seedvr2_submodule_dir", "seedvr2_model_dir"],
  project_defaults: [
    "caption_model_id",
    "caption_model_task",
    "t2i_model_id",
    "vae_model_id",
    "coverage_embedding_model",
    "seedvr2_dit_model",
    "caption_model_type",
  ],
};

// `hf_home` is the one field whose control name differs from its stored key.
const STORED_KEY = { hf_home: "home" };

/** Fill every control from a settings document. */
export function applySettings(modal, settings) {
  for (const [group, names] of Object.entries(GROUPS)) {
    for (const name of names) {
      const el = modal.querySelector(`[data-setting="${name}"]`);
      if (!el) continue;
      const value = (settings[group] || {})[STORED_KEY[name] || name];
      el.value = value == null ? "" : String(value);
    }
  }
}

/** Read every control back into a payload for `save_settings`. */
export function collectSettings(modal) {
  const payload = {};
  for (const [group, names] of Object.entries(GROUPS)) {
    payload[group] = {};
    for (const name of names) {
      const el = modal.querySelector(`[data-setting="${name}"]`);
      const value = el ? el.value.trim() : "";
      // Empty means "not configured"; sending null keeps that unambiguous on
      // the Python side, where None is the only unset marker.
      payload[group][STORED_KEY[name] || name] = value || null;
    }
  }
  return payload;
}
