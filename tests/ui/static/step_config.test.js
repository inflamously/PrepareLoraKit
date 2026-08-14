import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { nextTick, setupInteractionDom } from "./interaction_helpers.js";

let showStepConfig;
let apiCalls;

const layer = () => document.getElementById("modalLayer");
const click = (id) =>
  layer()
    .querySelector(`#${id}`)
    .dispatchEvent(new window.MouseEvent("click", { bubbles: true }));

/** The field wrapper carrying `label`, addressed the way a user sees it. */
const fieldFor = (label) =>
  [...layer().querySelectorAll(".step-config__field")].find(
    (wrap) => wrap.querySelector(".step-config__label")?.textContent === label,
  );
const selectFor = (label) => fieldFor(label).querySelector("select");
const customFor = (label) => fieldFor(label).querySelector(".step-config__custom");

const CAPTION_MODELS = [
  { value: "Qwen/Qwen3.8-27B", label: "Qwen3.8 27B (24 GB+)" },
  { value: "Qwen/Qwen3-VL-8B-Instruct", label: "Qwen3-VL 8B" },
];

/** A CaptionBboxStep-shaped schema: one nullable model select, one plain select. */
function captionFields() {
  return [
    {
      name: "caption_model_id",
      label: "Caption model",
      control: "select",
      value_type: "str",
      options: CAPTION_MODELS,
      allow_custom: true,
      nullable: true,
      placeholder: "Hugging Face model id",
      help: "",
    },
    {
      name: "caption_model_task",
      label: "Caption task",
      control: "select",
      value_type: "str",
      options: [
        { value: "auto", label: "Auto" },
        { value: "image-to-text", label: "Image to text" },
      ],
      allow_custom: false,
      nullable: false,
      placeholder: "",
      help: "",
    },
  ];
}

function open(values = {}, fields = captionFields()) {
  showStepConfig(
    { id: "config-1", kind: "step_config", payload: { step_type: "CaptionBboxStep", fields, values } },
    { onSubmitted: async () => {} },
  );
}

const submittedOverrides = () => apiCalls.submitted.at(-1).value.overrides;

describe("step config modal", () => {
  beforeEach(async () => {
    ({ apiCalls } = setupInteractionDom());
    ({ showStepConfig } = await import(
      "../../../prepare_lora_kit_ui/static/steps/step_config/step_config.js"
    ));
  });

  it("leaves an unset nullable field unset instead of preselecting a model", async () => {
    open({ caption_model_id: null, caption_model_task: "auto" });

    const select = selectFor("Caption model");
    assert.equal(select.value, "", "an unset model must not arrive preselected");
    assert.equal(select.options[0].value, "");
    assert.match(select.options[0].textContent, /Not set/);
    assert.ok(customFor("Caption model").classList.contains("hidden"));

    click("stepConfigContinue");
    await nextTick();
    assert.equal(submittedOverrides().caption_model_id, "");
  });

  it("pre-selects a stored value from the catalog", async () => {
    open({ caption_model_id: "Qwen/Qwen3-VL-8B-Instruct", caption_model_task: "auto" });

    assert.equal(selectFor("Caption model").value, "Qwen/Qwen3-VL-8B-Instruct");
    assert.ok(customFor("Caption model").classList.contains("hidden"));
  });

  it("routes a stored value the catalog lacks into the custom box", async () => {
    open({ caption_model_id: "acme/private-vlm", caption_model_task: "auto" });

    assert.equal(selectFor("Caption model").value, "__custom__");
    const custom = customFor("Caption model");
    assert.equal(custom.value, "acme/private-vlm");
    assert.ok(!custom.classList.contains("hidden"));

    click("stepConfigContinue");
    await nextTick();
    assert.equal(submittedOverrides().caption_model_id, "acme/private-vlm");
  });

  it("clears a stored model back to unset", async () => {
    open({ caption_model_id: "Qwen/Qwen3.8-27B", caption_model_task: "auto" });

    const select = selectFor("Caption model");
    select.value = "";
    select.dispatchEvent(new window.Event("change", { bubbles: true }));
    click("stepConfigContinue");
    await nextTick();

    assert.equal(submittedOverrides().caption_model_id, "");
  });

  it("keeps the first option for a non-nullable select with no stored value", async () => {
    open({ caption_model_id: null, caption_model_task: null });

    const select = selectFor("Caption task");
    assert.equal(select.value, "auto", "a required enum has no 'unset' to fall back to");
    assert.equal(select.querySelector('option[value=""]'), null);
  });

  it("submits nothing when the user asks for the defaults", async () => {
    open({ caption_model_id: "Qwen/Qwen3.8-27B", caption_model_task: "auto" });

    click("stepConfigDefaults");
    await nextTick();

    assert.deepEqual(submittedOverrides(), {});
  });
});
