import { api } from "../../core/api.js";
import { stepLabel } from "../../core/dom.js";
import { state } from "../../+state/index.js";
import { closeModal, showModal } from "../../components/modal.js";

const CUSTOM = "__custom__";

// Render the mid-run, pre-step config modal. The run thread is paused waiting on
// `pending`; submitting resolves it with the edited overrides and continues.
export function showStepConfig(pending, { onSubmitted }) {
  const { step_type: stepType, fields = [], values = {}, error } = pending.payload;

  const strip = document.createElement("div");
  strip.className = "modal step-config";
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
  const controls = fields.map((spec) => buildField(spec, values[spec.name]));
  row.replaceChildren(...controls.map((control) => control.element));

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
  return inputField(spec, value, wrap);
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
