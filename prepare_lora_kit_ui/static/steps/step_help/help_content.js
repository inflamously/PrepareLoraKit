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
      { id: "import_images", label: "Import source images",
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
      { id: "score_images", label: "Score images",
        desc: "Runs the automatic quality scorers and decides pass/fail for each image." },
      { id: "review_decisions", label: "Review decisions",
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
      { id: "duplicate_check", label: "Duplicate check",
        desc: "Detects near-identical images using a perceptual hash." },
      { id: "clip_scan", label: "CLIP scan",
        desc: "Optional: builds the coverage map using an AI embedding model." },
      { id: "drop_images", label: "Drop images",
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
      { id: "select_upscale_candidates", label: "Select candidates",
        desc: "Picks the images smaller than the target size that need upscaling." },
      { id: "upscale_images", label: "Upscale images",
        desc: "Runs the chosen upscaler on the selected images." },
      { id: "hallucination_check", label: "Hallucination check",
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
      { id: "reconstruct_images", label: "Reconstruct images",
        desc: "Compresses and rebuilds each image through the VAE and measures the detail loss." },
      { id: "review_vae_artifacts", label: "Review artifacts",
        desc: "Shows the flagged images with difference previews so you can decide on each." },
      { id: "apply_vae_decisions", label: "Apply decisions",
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
        desc: "Shrink images to this longest side before testing, to save VRAM. Blank = step default." },
      { label: "Seed",
        desc: "Random seed so the reconstruction is repeatable run to run." },
    ],
  },

  CaptionBboxStep: {
    summary: "Writes a text caption for each image to train the LoRA on.",
    detail:
      "Sends each image to a vision-language model to produce a description, then saves it as a " +
      "matching .txt file. You can optionally mark regions of interest first, and a sample of " +
      "captions is spot-checked for quality.",
    substeps: [
      { id: "annotate_regions", label: "Annotate regions",
        desc: "Optional: draw boxes on areas you want the caption to focus on." },
      { id: "caption_images", label: "Caption images",
        desc: "Generates a caption for each image and saves it as a .txt sidecar file." },
      { id: "validate_captions", label: "Validate captions",
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
      { id: "check_pairing", label: "Pairing",
        desc: "Checks every image has one caption and every caption has one image." },
      { id: "check_corrupt_files", label: "Corrupt files",
        desc: "Opens each image to catch truncated or unreadable files." },
      { id: "check_caption_quality", label: "Caption quality",
        desc: "Flags empty captions and ones that are too short or too long." },
      { id: "check_resolution", label: "Resolution",
        desc: "Flags images smaller than the configured training side." },
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
      { label: "Min training side (px)",
        desc: "Minimum image side for the resolution gate." },
      { label: "Caption model type",
        desc: "Caption-family hint for caption quality checks." },
    ],
  },

  BucketPoolsCheckStep: {
    summary: "Previews how images get grouped by resolution before training.",
    detail:
      "Simulates ai-toolkit's resolution bucketing without training. It assigns each image to its " +
      "closest bucket and flags \"thin\" buckets with too few images, suggesting fixes.",
    substeps: [
      { id: "assign_bucket_pools", label: "Assign buckets",
        desc: "Places each image in its closest aspect-ratio/resolution bucket." },
      { id: "report_thin_buckets", label: "Report thin buckets",
        desc: "Flags buckets with too few images and suggests crops or repeats." },
      { id: "write_cache_info", label: "Cache info",
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
