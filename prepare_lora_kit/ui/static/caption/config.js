import { $ } from "../core/dom.js";
import { state } from "../core/state.js";

function captionStepConfig() {
  const step = state.project?.steps.find((item) => item.type === "CaptionStep");
  return step?.config || null;
}

export function applyCaptionConfigDefaults() {
  const cfg = captionStepConfig();
  if (!cfg) return;

  const model = cfg.qwen_model_id || "Qwen/Qwen2-VL-7B-Instruct";
  const preset = $("captionModelPreset");
  const known = Array.from(preset.options).some(
    (option) => option.value === model,
  );

  preset.value = known ? model : "custom";
  $("captionModelCustom").value = known ? "" : model;

  const vramMap = {
    auto: "auto",
    low: "4bit",
    mid: "8bit",
    high: "none",
    max: "none",
  };
  $("captionVramMode").value = vramMap[cfg.vram_tier] || "auto";
}

export function resetCaptionConfigDefaults() {
  $("captionModelPreset").value = "Qwen/Qwen2-VL-7B-Instruct";
  $("captionModelCustom").value = "";
  $("captionVramMode").value = "auto";
}

export function syncCaptionModelInput() {
  if ($("captionModelPreset").value !== "custom") {
    $("captionModelCustom").value = "";
  }
}

export function selectedCaptionModel() {
  const preset = $("captionModelPreset").value;
  return preset === "custom" ? $("captionModelCustom").value.trim() : preset;
}
