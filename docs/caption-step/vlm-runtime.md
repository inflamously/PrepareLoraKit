# Model runtime (`vlm.py`)

Part of the [Caption Step reference](README.md).

**Backend-generic Hugging Face transformers**, not tied to one model family.
`task` is `auto | image-text-to-text | image-to-text`, and `auto` tries both
adapters in order:

- `image-text-to-text` — requires `processor.apply_chat_template`. Model class
  tried in order: `AutoModelForImageTextToText` →
  `Qwen2VLForConditionalGeneration`. Sets `supports_prompt=True`.
- `image-to-text` — `AutoModelForImageTextToText` → `BlipForConditionalGeneration` →
  `VisionEncoderDecoderModel` → `AutoModelForCausalLM`. `supports_prompt=False`,
  so the caption is composed post-hoc (labels and the token are appended). Florence
  gets the special `<MORE_DETAILED_CAPTION>` task prompt.

Characteristics worth knowing:

- **No batching.** Strictly one image per `generate()` call, greedy
  (`do_sample=False`).
- **Remote code is denied by default.** Every `from_pretrained` here — the model
  classes *and* `_load_processor`, since a custom image processor is code too —
  passes `trust_remote_code=_trust_remote_code()`, which is
  `hub.remote_code_allowed()`. See [settings](../settings.md#allow_remote_code).
  A refusal becomes `RemoteCodeNotAllowed`, and `_fatal_load_error` stops the
  adapter walk on it (as it already did for gated repos) rather than burying it
  in the joined "could not load with supported adapters" message.
- **Reasoning models.** `_build_chat_text` renders the prompt with
  `enable_thinking=False`, retrying without the kwarg for processors that validate
  their signature. Because a template may ignore it, `_finalize_caption` also runs
  `caption_text.strip_reasoning` over every generation before `strip_boilerplate`
  — it removes a closed `<think>…</think>` block, a stray `</think>` (templates
  that enable thinking append the opener to the *prompt*, so only the close is
  decoded), and a stray `<think>` left by a thought that `max_new_tokens` cut off.
  The last case yields an empty caption by design: a truncated thought is not a
  caption, and it would otherwise be written to the training `.txt`. Both
  `_run_prompted` and `_run_image_to_text` return through `_finalize_caption`, so
  no pass can bypass it; a pass that strips to nothing logs a one-time warning.
- **Lazy imports.** `torch`, `transformers` and `PIL` are imported inside
  functions, and `__init__.py` is a `__getattr__` shim, so nothing heavy loads
  until the step actually runs.
- **Caching.** Module-level `_CACHE` keyed by
  `(model_id, task, quantization, dtype, max_pixels)`, so region captions and
  full-image captions reuse one loaded model.
- **Thread safety.** `load()` is guarded by a `threading.Lock` because the UI's
  region-caption call arrives on a different thread than the pipeline loop.
- **Device.** `device_map="auto"` with `low_cpu_mem_usage=True`; `_input_device()`
  sniffs params → buffers → `model.device` → cuda/cpu fallback. `_resolve_dtype`
  forces float32 without CUDA.
- **Quantization.** `CaptionBboxConfig._VRAM_TIERS` maps the project's `vram_tier`
  to `(quantization, dtype)`: `low`→4bit, `mid`→8bit, `high`/`max`→none. The
  `auto` quantization mode instead picks 4bit ≤16 GB VRAM, 8bit ≤32 GB, else none.
  4-bit uses `BitsAndBytesConfig` nf4 with double quant, and 4/8-bit require CUDA
  plus bitsandbytes.
- **OOM defense.** `_DEFAULT_MAX_PIXELS = 1024 * 1024` area budget with a LANCZOS
  downscale before the processor, and a CUDA cache clear in the `finally` of every
  generate.

**This step runs in-process.** Unlike SeedVR2 upscaling
(`steps/upscale/seedvr2_worker.py`), there is no worker subprocess. VRAM hygiene
between steps comes from `release_accelerator_memory()` in
`pipeline/execution/engine.py` plus `runtime.unload()`.
