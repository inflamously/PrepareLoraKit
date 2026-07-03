// Plain-language help for each pipeline step, keyed by `step.type`.
// Shown by the per-step "?" button (see step_help.js). Keep every `desc` to one
// short, jargon-free line so the help modal stays scannable. Substep ids/labels
// mirror project/pipeline/substeps.py; param labels mirror the FieldSpec labels in
// project/config_schema/steps/*.py. Steps with no tunable params omit `params`.
export const STEP_HELP = {
  ImportStep: {
    summary: "Brings your source images into the project to work on.",
    detail:
      "Copies the images from your input folder into the project's working dataset, " +
      "leaving your originals untouched. Everything after this point operates on the copy.",
    substeps: [
      { id: "s0_import", label: "Import source images",
        desc: "Copies supported image files (jpg, png, webp, etc.) into the working dataset." },
    ],
  },

  QualityGateStep: {
    summary: "Filters out low-quality images before you spend effort on them.",
    detail:
      "Automatically scores every image (sharpness, noise, size, watermarks, and more) " +
      "and marks the ones that fail. You can then review those decisions in a gallery and " +
      "override anything before the rejects are dropped.",
    substeps: [
      { id: "s1_1_score", label: "Score images",
        desc: "Runs the automatic quality scorers and decides pass/fail for each image." },
      { id: "s1_2_decide", label: "Review decisions",
        desc: "Opens a gallery so you can confirm or flip the auto pass/fail choices." },
    ],
    params: [
      { label: "Manual review",
        desc: "Show the review gallery so you can adjust the automatic decisions." },
      { label: "Auto only (skip manual review)",
        desc: "Trust the automatic scores and skip the gallery entirely." },
      { label: "Review every image",
        desc: "Put every image into the gallery, not just the ones that failed." },
    ],
  },

  CurateStep: {
    summary: "Removes duplicates and near-duplicates and checks dataset coverage.",
    detail:
      "Finds and drops repeated or near-identical images, then builds a coverage map so you " +
      "can see if your dataset is varied or clustered.",
    substeps: [
      { id: "s2_1_dupecheck", label: "Duplicate check",
        desc: "Detects near-identical images using a perceptual hash." },
      { id: "s2_2_clipscan", label: "CLIP scan",
        desc: "Optional: builds the coverage map using an AI embedding model." },
      { id: "s2_3_drop_images", label: "Drop images",
        desc: "Removes the duplicates you chose to discard." },
    ],
    params: [
      { label: "Dedup hamming distance",
        desc: "How similar two images must be to count as duplicates. Lower = stricter (8 is typical)." },
      { label: "Skip CLIP coverage",
        desc: "Turn off the AI coverage scan to save time and VRAM." },
      { label: "Coverage embedding model",
        desc: "Which AI model builds the coverage map. \"Auto\" picks one based on your VRAM." },
      { label: "PCA→UMAP switch",
        desc: "Dataset size at which the coverage plot switches from PCA to UMAP layout." },
    ],
  },

  UpscaleStep: {
    summary: "Enlarges images that are too small, then checks the result is faithful.",
    detail:
      "Optional step. Upscales images below your target resolution using the chosen upscaler, " +
      "then re-checks them to reject results where the upscaler invented fake texture or detail.",
    substeps: [
      { id: "s3_1_select_candidates", label: "Select candidates",
        desc: "Picks the images smaller than the target size that need upscaling." },
      { id: "s3_2_upscale", label: "Upscale images",
        desc: "Runs the chosen upscaler on the selected images." },
      { id: "s3_3_hallucination_check", label: "Hallucination check",
        desc: "Rejects upscaled images that drifted too far from the original (invented detail)." },
    ],
    params: [
      { label: "Upscale model",
        desc: "Which upscaler to use: SeedVR2 (AI), Lanczos (classic), or a custom one." },
      { label: "Target side (px)",
        desc: "The size, in pixels, the longest side should reach after upscaling." },
      { label: "Hallucination SSIM",
        desc: "Minimum similarity to the original (0–1). Lower allows more change before rejecting." },
      { label: "SeedVR2 DiT model",
        desc: "The SeedVR2 model file to load. Leave blank to use the default." },
      { label: "SeedVR2 residency",
        desc: "Where the model lives: Auto, GPU (fast), or CPU (saves VRAM, slower)." },
      { label: "SeedVR2 batch size",
        desc: "How many images SeedVR2 processes at once. Higher uses more VRAM." },
    ],
  },

  VaeGateStep: {
    summary: "Catches images the model can't reproduce well before training on them.",
    detail:
      "Runs every image through the target model's VAE (its built-in image compressor) and " +
      "back again, then measures how much fine detail was lost. Images that come back noticeably " +
      "degraded are flagged so you can keep, drop, or replace them — because the model would " +
      "struggle to learn from them as-is.",
    substeps: [
      { id: "s4_1_reconstruct", label: "Reconstruct images",
        desc: "Compresses and rebuilds each image through the VAE and measures the detail loss." },
      { id: "s4_2_review", label: "Review artifacts",
        desc: "Shows the flagged images with difference previews so you can decide on each." },
      { id: "s4_3_apply_decisions", label: "Apply decisions",
        desc: "Keeps, drops, or replaces images based on your review choices." },
    ],
    params: [
      { label: "Diff amplification",
        desc: "How strongly the preview exaggerates differences so they're easier to see." },
      { label: "Gaussian blur sigma",
        desc: "Smoothing applied when building the difference map (higher = smoother)." },
      { label: "Gaussian blur kernel (odd)",
        desc: "Size of the blur window in pixels. Must be an odd number." },
      { label: "Otsu thresholding",
        desc: "Automatically pick the cutoff that separates damaged areas from clean ones." },
      { label: "Outlier sigma",
        desc: "How far above average the detail loss must be to flag an image (2 = mean + 2σ)." },
      { label: "HF cutoff fraction",
        desc: "Which slice of high-frequency detail is measured for loss (0–0.5)." },
      { label: "Max side (px)",
        desc: "Shrink images to this longest side before testing, to save VRAM. Blank = network default." },
      { label: "Seed",
        desc: "Random seed so the reconstruction is repeatable run to run." },
    ],
  },

  CaptionStep: {
    summary: "Writes a text caption for each image to train the LoRA on.",
    detail:
      "Sends each image to a vision-language model to produce a description, then saves it as a " +
      "matching .txt file. You can optionally mark regions of interest first, and a sample of " +
      "captions is spot-checked for quality.",
    substeps: [
      { id: "s5_1_annotate", label: "Annotate regions",
        desc: "Optional: draw boxes on areas you want the caption to focus on." },
      { id: "s5_2_caption", label: "Caption images",
        desc: "Generates a caption for each image and saves it as a .txt sidecar file." },
      { id: "s5_3_validate", label: "Validate captions",
        desc: "Spot-checks a sample of captions so you can catch bad ones." },
    ],
    params: [
      { label: "Caption model",
        desc: "Which vision-language model writes the captions (e.g. Qwen3-VL, JoyCaption)." },
      { label: "Caption task",
        desc: "How the model is prompted. \"Auto\" picks the right mode for the chosen model." },
      { label: "VRAM tier",
        desc: "Matches the model's memory use to your GPU. \"Auto\" detects it for you." },
      { label: "Max new tokens",
        desc: "Maximum length of each generated caption, in tokens." },
      { label: "Spot check fraction",
        desc: "Share of captions to show you for review, from 0 to 1 (0.10 = 10%)." },
    ],
  },

  AuditStep: {
    summary: "Final integrity check that the dataset is ready to train.",
    detail:
      "Verifies that every image has exactly one caption, no files are corrupt, captions aren't " +
      "empty or wildly long, and no image is below the minimum training resolution.",
    substeps: [
      { id: "s6_1_pairing", label: "Pairing",
        desc: "Checks every image has one caption and every caption has one image." },
      { id: "s6_2_corrupt", label: "Corrupt files",
        desc: "Opens each image to catch truncated or unreadable files." },
      { id: "s6_3_caption_quality", label: "Caption quality",
        desc: "Flags empty captions and ones that are too short or too long." },
      { id: "s6_4_resolution", label: "Resolution",
        desc: "Flags images smaller than the largest training bucket." },
    ],
    params: [
      { label: "Min caption length",
        desc: "Captions shorter than this (in characters) are flagged." },
      { label: "Max caption length",
        desc: "Captions longer than this (in characters) are flagged." },
      { label: "Check pairing",
        desc: "Enable the image↔caption pairing check." },
      { label: "Check corrupt files",
        desc: "Enable the corrupt/unreadable file check." },
      { label: "Check caption length",
        desc: "Enable the caption length check." },
      { label: "Check resolution gate",
        desc: "Enable the minimum-resolution check." },
    ],
  },

  ConfigGenStep: {
    summary: "Generates the training config file for your dataset.",
    detail:
      "Builds an ai-toolkit-compatible YAML config from your network profile, dataset stats, and " +
      "training intent, so you can hand it straight to the trainer.",
    substeps: [
      { id: "s7_1_dataset_stats", label: "Dataset stats",
        desc: "Counts images and works out repeats and other dataset numbers." },
      { id: "s7_2_build_config", label: "Build config",
        desc: "Assembles the training settings from the network profile and stats." },
      { id: "s7_3_write_config", label: "Write config",
        desc: "Writes the final YAML config file to disk." },
    ],
    params: [
      { label: "Base template path",
        desc: "Optional YAML to start from instead of the built-in template." },
    ],
  },

  BucketDryRunStep: {
    summary: "Previews how images get grouped by resolution before training.",
    detail:
      "Simulates ai-toolkit's resolution bucketing without training. It assigns each image to its " +
      "closest bucket and flags \"thin\" buckets with too few images, suggesting fixes.",
    substeps: [
      { id: "s8_1_assign_buckets", label: "Assign buckets",
        desc: "Places each image in its closest aspect-ratio/resolution bucket." },
      { id: "s8_2_report_thin_buckets", label: "Report thin buckets",
        desc: "Flags buckets with too few images and suggests crops or repeats." },
      { id: "s8_3_cache_info", label: "Cache info",
        desc: "Optional: writes a cache_info.json to speed up the real training run." },
    ],
    params: [
      { label: "Thin bucket threshold",
        desc: "Buckets with this many images or fewer are flagged as thin (2 is typical)." },
      { label: "Write cache_info.json",
        desc: "Also write the cache manifest ai-toolkit can reuse on the real run." },
    ],
  },
};
