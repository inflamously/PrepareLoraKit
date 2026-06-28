import { api } from "../../core/api.js";
import { stepLabel } from "../../core/dom.js";
import { state } from "../../+state/index.js";
import { closeModal, modalCancelButton, showModal } from "../../components/modal.js";

const CUSTOM = "__custom__";

// Render the mid-run, pre-step config modal. The run thread is paused waiting on
// `pending`; submitting resolves it with the edited overrides and continues.
export function showStepConfig(pending, { onSubmitted }) {
  const { step_type: stepType, fields = [], values = {}, error } = pending.payload;

  const strip = document.createElement("div");
  strip.className = "modal modal--compact step-config";
  strip.innerHTML = `
    <div class="step-config__head">
      <div>
        <h2>${stepLabel(stepType)} config</h2>
        <p>Adjust values for this step, then continue.</p>
      </div>
      <div class="step-config__actions">
        <button class="secondary" id="stepConfigDefaults">Use defaults</button>
        <button class="primary" id="stepConfigContinue">Continue</button>
      </div>
    </div>
    <p class="step-config__error ${error ? "" : "hidden"}">${error || ""}</p>
    <div class="step-config__fields" role="group"></div>
  `;

  const row = strip.querySelector(".step-config__fields");
  const hasPrompts = fields.some((f) => f.control === "prompt");
  const controls = fields.map((spec) => ({
    ...buildField(spec, values[spec.name]),
    control: spec.control,
  }));

  // Caption-style configs (with large prompt fields) get a wider, two-column
  // layout: plain settings on the left, prompt fields on the right. Other step
  // configs keep the compact single-column layout.
  if (hasPrompts) {
    strip.classList.add("step-config--wide");
    const left = document.createElement("div");
    left.className = "step-config__col";
    const right = document.createElement("div");
    right.className = "step-config__col step-config__col--prompts";
    for (const control of controls) {
      (control.control === "prompt" ? right : left).append(control.element);
    }
    row.replaceChildren(left, right);
  } else {
    row.replaceChildren(...controls.map((control) => control.element));
  }

  const submit = async (overrides) => {
    await api().submit_interaction(state.jobId, pending.id, { overrides });
    closeModal();
    await onSubmitted();
  };

  strip.querySelector("#stepConfigContinue").addEventListener("click", () => {
    const overrides = {};
    for (const control of controls) overrides[control.name] = control.read();
    submit(overrides);
  });
  strip.querySelector("#stepConfigDefaults").addEventListener("click", () => submit({}));

  const actions = strip.querySelector(".step-config__actions");
  actions.insertBefore(modalCancelButton(onSubmitted), actions.firstChild);

  showModal(strip);
}

function buildField(spec, value) {
  const wrap = document.createElement("label");
  wrap.className = "step-config__field";

  const label = document.createElement("span");
  label.className = "step-config__label";
  label.textContent = spec.label;
  label.title = spec.help || "";
  wrap.append(label);

  if (spec.control === "checkbox") {
    return checkboxField(spec, value, wrap);
  }
  if (spec.control === "select") {
    return selectField(spec, value, wrap);
  }
  if (spec.control === "prompt") {
    return promptField(spec, value, wrap);
  }
  return inputField(spec, value, wrap);
}

// A saved-prompt dropdown + editable textarea backed by the global caption
// prompt library. Picking an entry fills the textarea; Save/Delete manage the
// library via the bridge. read() returns the textarea text used for this run
// (blank → coerced to None → built-in default prompt).
function promptField(spec, value, wrap) {
  const kind = spec.name === "region_prompt" ? "region" : "full_image";
  wrap.classList.add("step-config__field--prompt");

  const select = document.createElement("select");
  select.className = "nf-select";

  const textarea = document.createElement("textarea");
  textarea.className = "nf-input step-config__prompt-text";
  textarea.rows = 6;
  if (spec.placeholder) textarea.placeholder = spec.placeholder;
  textarea.value = value == null ? "" : String(value);

  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.className = "nf-input step-config__prompt-name";
  nameInput.placeholder = "Prompt name";

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "secondary";
  saveBtn.textContent = "Save";

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "secondary";
  deleteBtn.textContent = "Delete";

  const actions = document.createElement("div");
  actions.className = "step-config__prompt-actions";
  actions.append(nameInput, saveBtn, deleteBtn);

  wrap.append(select, textarea, actions);

  // name → text for the currently-loaded library entries.
  let saved = new Map();
  const BLANK = "";

  const populate = (prompts, selectName) => {
    saved = new Map(prompts.map((p) => [p.name, p.text]));
    select.replaceChildren(new Option("— custom / unsaved —", BLANK));
    for (const p of prompts) select.append(new Option(p.name, p.name));
    if (selectName && saved.has(selectName)) {
      select.value = selectName;
      nameInput.value = selectName;
    } else {
      select.value = BLANK;
    }
  };

  const refresh = async (selectName) => {
    try {
      const res = await api().list_caption_prompts(kind);
      populate(res.prompts || [], selectName);
    } catch (err) {
      populate([], selectName);
    }
  };

  select.addEventListener("change", () => {
    const name = select.value;
    if (name && saved.has(name)) {
      textarea.value = saved.get(name);
      nameInput.value = name;
    }
  });

  saveBtn.addEventListener("click", async () => {
    const name = nameInput.value.trim();
    if (!name) {
      nameInput.focus();
      return;
    }
    await api().save_caption_prompt(kind, name, textarea.value);
    await refresh(name);
  });

  deleteBtn.addEventListener("click", async () => {
    const name = nameInput.value.trim() || select.value;
    if (!name) return;
    await api().delete_caption_prompt(kind, name);
    nameInput.value = "";
    await refresh(BLANK);
  });

  // Render now, populate async. If the current text matches a saved prompt,
  // preselect it so the dropdown reflects what's in the textarea.
  refresh().then(() => {
    const current = textarea.value.trim();
    if (!current) return;
    for (const [name, text] of saved) {
      if (text.trim() === current) {
        select.value = name;
        nameInput.value = name;
        break;
      }
    }
  });

  return { name: spec.name, element: wrap, read: () => textarea.value };
}

function checkboxField(spec, value, wrap) {
  const input = document.createElement("input");
  input.type = "checkbox";
  input.className = "nf-check step-config__check";
  input.checked = Boolean(value);
  wrap.classList.add("step-config__field--check");
  wrap.append(input);
  return { name: spec.name, element: wrap, read: () => input.checked };
}

function selectField(spec, value, wrap) {
  const select = document.createElement("select");
  select.className = "nf-select";
  const knownValues = spec.options.map((option) => option.value);
  for (const option of spec.options) {
    select.append(new Option(option.label, option.value));
  }

  let custom = null;
  if (spec.allow_custom) {
    select.append(new Option("Custom…", CUSTOM));
    custom = document.createElement("input");
    custom.type = "text";
    custom.className = "nf-input step-config__custom";
    custom.placeholder = spec.placeholder || "Custom value";
  }

  const current = value == null ? "" : String(value);
  if (current && knownValues.includes(current)) {
    select.value = current;
  } else if (current && spec.allow_custom) {
    select.value = CUSTOM;
    custom.value = current;
  } else {
    select.value = knownValues.includes("") ? "" : select.options[0]?.value || "";
  }

  const syncCustom = () => {
    if (!custom) return;
    custom.classList.toggle("hidden", select.value !== CUSTOM);
  };
  select.addEventListener("change", syncCustom);

  wrap.append(select);
  if (custom) {
    wrap.append(custom);
    syncCustom();
  }

  return {
    name: spec.name,
    element: wrap,
    read: () => (select.value === CUSTOM ? custom.value.trim() : select.value),
  };
}

function inputField(spec, value, wrap) {
  const input = document.createElement("input");
  input.className = "nf-input";
  input.type = spec.control === "number" ? "number" : "text";
  if (spec.placeholder) input.placeholder = spec.placeholder;
  if (spec.minimum != null) input.min = spec.minimum;
  if (spec.maximum != null) input.max = spec.maximum;
  if (spec.step != null) input.step = spec.step;
  input.value = value == null ? "" : String(value);
  wrap.append(input);
  return { name: spec.name, element: wrap, read: () => input.value };
}
