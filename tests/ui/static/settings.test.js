import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { nextTick, setupInteractionDom } from "./interaction_helpers.js";

let openSettingsModal;
let calls;

const layer = () => document.getElementById("modalLayer");
const field = (name) => layer().querySelector(`[data-setting="${name}"]`);
const click = (id) =>
  layer()
    .querySelector(`#${id}`)
    .dispatchEvent(new window.MouseEvent("click", { bubbles: true }));

function settingsPayload(overrides = {}) {
  return {
    settings: {
      version: 1,
      huggingface: { home: null },
      hardware: {
        vram_tier: null,
        cuda_device: null,
        seedvr2_submodule_dir: null,
        seedvr2_model_dir: null,
      },
      project_defaults: {
        caption_model_id: null,
        caption_model_task: null,
        t2i_model_id: null,
        vae_model_id: null,
        coverage_embedding_model: null,
        seedvr2_dit_model: null,
        caption_model_type: null,
      },
      ...overrides,
    },
    choices: {
      caption_model_id: [{ value: "Qwen/Qwen3-VL-8B-Instruct", label: "Qwen3-VL 8B" }],
      caption_model_task: [{ value: "auto", label: "Auto" }],
      t2i_model_id: [{ value: "auto", label: "Auto" }],
      coverage_embedding_model: [{ value: "ViT-B-32", label: "ViT-B-32" }],
      seedvr2_dit_model: [
        { value: "auto", label: "Auto (match VRAM)" },
        { value: "seedvr2_ema_3b_fp8_e4m3fn.safetensors", label: "3B fp8" },
      ],
      caption_model_type: [{ value: "clip", label: "CLIP" }],
      vram_tier: [
        { value: "low", label: "Low (<=16 GB)" },
        { value: "mid", label: "Mid (<=24 GB)" },
        { value: "high", label: "High (<=32 GB)" },
        { value: "max", label: "Max (>32 GB)" },
      ],
    },
    placeholders: {
      hf_home: "~/.cache/huggingface",
      vram_tier: "auto (detect at run time)",
      cuda_device: "0",
      seedvr2_submodule_dir: "/repo/third_party/seedvr2",
      seedvr2_model_dir: "~/.cache/prepare_lora_kit/seedvr2",
      caption_model_id: "required — a run fails without one",
      caption_model_task: "auto",
      t2i_model_id: "auto",
      vae_model_id: "black-forest-labs/FLUX.2-klein-base-9B",
      coverage_embedding_model: "auto",
      seedvr2_dit_model: "auto",
      caption_model_type: "auto",
    },
    vram_tiers: ["low", "mid", "high", "max"],
    settings_path: "/home/u/.prepare_lora_kit/settings.yaml",
    login_command: "hf auth login",
    model_ids: ["black-forest-labs/FLUX.2-klein-base-9B"],
  };
}

function stubSettingsApi(overrides = {}) {
  const record = {
    saved: [],
    checked: [],
    detects: 0,
    hfStatuses: 0,
    saveHandler: null,
    payload: settingsPayload(),
  };
  Object.assign(window.pywebview.api, {
    get_settings: async () => record.payload,
    save_settings: async (payload) => {
      record.saved.push(payload);
      if (record.saveHandler) return record.saveHandler(payload);
      return record.payload;
    },
    hf_status: async () => {
      record.hfStatuses += 1;
      return {
        token: { present: true, source: "stored", error: null },
        account: { ok: true, name: "nflamously", error: null },
        login_command: "hf auth login",
      };
    },
    check_model_access: async (repoIds) => {
      record.checked.push(repoIds);
      return {
        results: (repoIds || []).map((repo_id) => ({
          repo_id,
          status: "gated",
          message: "gated — accept the licence",
          url: `https://huggingface.co/${repo_id}`,
        })),
      };
    },
    detect_hardware: async () => {
      record.detects += 1;
      return { cuda: true, total_vram_gb: 31.4, suggested_tier: "high" };
    },
    choose_folder: async () => ({ path: "/picked/folder" }),
    ...overrides,
  });
  return record;
}

describe("settings modal", () => {
  let record;

  beforeEach(async () => {
    ({ calls } = await import("./interaction_helpers.js"));
    setupInteractionDom();
    record = stubSettingsApi();
    ({ openSettingsModal } = await import(
      "../../../prepare_lora_kit_ui/static/settings/settings.js"
    ));
  });

  it("renders three sections and every configurable field", async () => {
    await openSettingsModal();

    const headings = [...layer().querySelectorAll(".settings-section h3")].map((h) =>
      h.textContent.trim(),
    );
    assert.deepEqual(headings, ["Hugging Face", "Hardware", "Defaults for new projects"]);
    for (const name of [
      "hf_home",
      "vram_tier",
      "cuda_device",
      "seedvr2_submodule_dir",
      "seedvr2_model_dir",
      "caption_model_id",
      "caption_model_task",
      "t2i_model_id",
      "vae_model_id",
      "coverage_embedding_model",
      "seedvr2_dit_model",
      "caption_model_type",
    ]) {
      assert.ok(field(name), `missing control for ${name}`);
    }
  });

  it("shows the app default as placeholder text so blank reads as 'not configured'", async () => {
    await openSettingsModal();

    assert.equal(field("vae_model_id").value, "");
    assert.equal(
      field("vae_model_id").getAttribute("placeholder"),
      "black-forest-labs/FLUX.2-klein-base-9B",
    );
    const unset = field("vram_tier").querySelector('option[value=""]');
    assert.match(unset.textContent, /Not set/);
  });

  it("never offers to store a token", async () => {
    await openSettingsModal();

    assert.equal(field("hf_token"), null);
    assert.equal(layer().querySelector('input[type="password"]'), null);
    assert.match(layer().textContent, /never stores a token/i);
  });

  it("shows the login command as a value, not as markup", async () => {
    record.payload.login_command = '</input><img onerror=alert(1) src=x>';
    await openSettingsModal();

    assert.equal(
      layer().querySelector("#settingsLoginCommand").value,
      '</input><img onerror=alert(1) src=x>',
    );
    assert.equal(
      [...layer().querySelectorAll("img")].filter((img) => img.hasAttribute("onerror")).length,
      0,
    );
  });

  it("pre-fills stored values", async () => {
    record.payload = settingsPayload({
      hardware: {
        vram_tier: "mid",
        cuda_device: "1",
        seedvr2_submodule_dir: "/opt/seedvr2",
        seedvr2_model_dir: null,
      },
      huggingface: { home: "/mnt/hf" },
    });
    await openSettingsModal();

    assert.equal(field("vram_tier").value, "mid");
    assert.equal(field("cuda_device").value, "1");
    assert.equal(field("seedvr2_submodule_dir").value, "/opt/seedvr2");
    assert.equal(field("seedvr2_model_dir").value, "");
    assert.equal(field("hf_home").value, "/mnt/hf");
  });

  it("saves the grouped payload and closes", async () => {
    await openSettingsModal();

    field("vram_tier").value = "low";
    field("caption_model_id").value = "Qwen/Qwen3-VL-4B-Instruct";
    click("settingsSave");
    await nextTick();

    assert.equal(record.saved.length, 1);
    assert.deepEqual(record.saved[0].hardware.vram_tier, "low");
    assert.equal(record.saved[0].project_defaults.caption_model_id, "Qwen/Qwen3-VL-4B-Instruct");
    assert.equal(record.saved[0].huggingface.home, null, "hf_home maps to huggingface.home");
    assert.equal(layer().querySelector(".settings-modal"), null, "modal should close on save");
  });

  it("sends null for a cleared field rather than an empty string", async () => {
    record.payload = settingsPayload({
      hardware: {
        vram_tier: "mid",
        cuda_device: "1",
        seedvr2_submodule_dir: null,
        seedvr2_model_dir: null,
      },
    });
    await openSettingsModal();

    field("cuda_device").value = "   ";
    click("settingsSave");
    await nextTick();

    assert.equal(record.saved[0].hardware.cuda_device, null);
  });

  it("shows an inline error and re-enables Save when the bridge rejects", async () => {
    record.saveHandler = () => {
      throw new Error("Traceback...\nValueError: vram_tier must be one of ['low']");
    };
    await openSettingsModal();

    click("settingsSave");
    await nextTick();

    assert.match(layer().querySelector("#settingsError").textContent, /vram_tier/);
    assert.ok(!layer().querySelector("#settingsSave").disabled);
    assert.ok(layer().querySelector(".settings-modal"), "modal stays open on failure");
  });

  it("closes without saving", async () => {
    await openSettingsModal();

    click("settingsCancel");
    await nextTick();

    assert.equal(record.saved.length, 0);
    assert.equal(layer().querySelector(".settings-modal"), null);
  });

  it("does not talk to the Hub or torch just to open", async () => {
    await openSettingsModal();

    assert.equal(record.hfStatuses, 0);
    assert.equal(record.checked.length, 0);
    assert.equal(record.detects, 0);
  });

  it("reports the signed-in account on demand", async () => {
    await openSettingsModal();

    click("settingsHfCheck");
    await nextTick();

    assert.equal(record.hfStatuses, 1);
    const status = layer().querySelector("#settingsHfStatus");
    assert.match(status.textContent, /Signed in as nflamously/);
    assert.equal(status.dataset.state, "ok");
  });

  it("tells the user how to sign in when there is no token", async () => {
    record = stubSettingsApi({
      hf_status: async () => ({
        token: { present: false, source: null, error: null },
        account: { ok: false, name: null, error: "No token found." },
        login_command: "hf auth login",
      }),
    });
    await openSettingsModal();

    click("settingsHfCheck");
    await nextTick();

    const status = layer().querySelector("#settingsHfStatus");
    assert.match(status.textContent, /hf auth login/);
    assert.equal(status.dataset.state, "warn");
  });

  it("checks the ids currently on screen, not the last saved ones", async () => {
    await openSettingsModal();

    field("caption_model_id").value = "typed/but-not-saved";
    field("t2i_model_id").value = "auto";
    field("vae_model_id").value = "/local/file.safetensors";
    click("settingsCheckModels");
    await nextTick();

    assert.deepEqual(record.checked, [["typed/but-not-saved"]]);
    assert.equal(record.saved.length, 0, "checking must not save");
  });

  it("renders one result row per model with its status", async () => {
    await openSettingsModal();

    field("caption_model_id").value = "some/model";
    click("settingsCheckModels");
    await nextTick();

    const items = layer().querySelectorAll(".settings-access__item");
    assert.equal(items.length, 1);
    assert.equal(items[0].dataset.state, "gated");
    assert.match(items[0].textContent, /some\/model/);
    assert.match(items[0].textContent, /accept the licence/);
  });

  it("says so when there is nothing to check", async () => {
    await openSettingsModal();

    click("settingsCheckModels");
    await nextTick();

    assert.match(layer().querySelector("#settingsAccessResults").textContent, /nothing to check/i);
  });

  it("fills the tier from a hardware probe", async () => {
    await openSettingsModal();

    click("settingsDetect");
    await nextTick();

    assert.equal(record.detects, 1);
    assert.equal(field("vram_tier").value, "high");
    assert.match(layer().querySelector("#settingsDetected").textContent, /31.4 GB/);
  });

  it("reports a machine with no GPU instead of guessing a tier", async () => {
    record = stubSettingsApi({
      detect_hardware: async () => ({ cuda: false, total_vram_gb: 0, suggested_tier: null }),
    });
    await openSettingsModal();

    click("settingsDetect");
    await nextTick();

    assert.match(layer().querySelector("#settingsDetected").textContent, /No CUDA GPU/);
    assert.equal(field("vram_tier").value, "");
  });

  it("fills a path field from the folder picker", async () => {
    await openSettingsModal();

    layer()
      .querySelector('[data-browse="seedvr2_model_dir"]')
      .dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    await nextTick();

    assert.equal(field("seedvr2_model_dir").value, "/picked/folder");
  });

  it("shows where the settings file lives", async () => {
    await openSettingsModal();

    assert.match(
      layer().querySelector(".settings-path").textContent,
      /\.prepare_lora_kit[\\/]settings\.yaml/,
    );
  });

  it("is not reachable from the pipeline interaction dispatcher", async () => {
    const controller = await import(
      "../../../prepare_lora_kit_ui/static/job/controller.js"
    );
    const source = controller.handlePendingInput
      ? String(controller.handlePendingInput)
      : "";

    assert.ok(!source.includes("settings"), "Settings must not be a pending-input kind");
    assert.ok(calls, "helper import sanity");
  });
});
