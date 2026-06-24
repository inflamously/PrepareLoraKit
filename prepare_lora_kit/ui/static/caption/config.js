import { $ } from "../core/dom.js";
import { state } from "../+state/index.js";

function captionStepConfig() {
  const step = state.project?.steps.find((item) => item.type === "CaptionStep");
  return step?.config || null;
}

export function applyCaptionConfigDefaults() {
  const cfg = captionStepConfig();
  if (!cfg) {
    resetCaptionConfigDefaults();
    return;
  }

  const model = cfg.caption_model_id || cfg.qwen_model_id || "";
  const preset = $("captionModelPreset");
  const known = Array.from(preset.options).some(
    (option) => option.value === model,
  );

  preset.value = model && known ? model : model ? "custom" : "";
  $("captionModelCustom").value = model && !known ? model : "";
  $("captionModelTask").value = cfg.caption_model_task || "auto";

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
  $("captionModelPreset").value = "";
  $("captionModelCustom").value = "";
  $("captionModelTask").value = "auto";
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

export function selectedCaptionTask() {
  return $("captionModelTask").value || "auto";
}
