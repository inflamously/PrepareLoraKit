# PrepareLoraKit Overview

PrepareLoraKit is a Python CLI for preparing image datasets for LoRA-style
training, with a focus on Flux and similar diffusion models. It takes an
original dataset folder, builds a separate working dataset, runs a configurable
sequence of preparation steps, and emits reports plus an ai-toolkit-compatible
training config.

The package installs a `plk` command via `pyproject.toml`. During local
development, the same CLI can also be launched with `python3 main.py` on POSIX
shells, or `python main.py` on Windows shells where `python` is available.

## Core Workflow

The main workflow is:

```bash
plk run --input /path/to/images --project example --token my_trigger
```

or, from the repository:

```bash
python3 main.py run --input /path/to/images --project example --token my_trigger
```

If `--output` is not supplied, output goes to:

```text
outputs/<input-folder-name>/
```

The original image folder is left untouched. Step 1 creates:

```text
outputs/<dataset-name>/dataset/
```

and later steps mutate that working dataset in place. Reports are written under:

```text
outputs/<dataset-name>/reports/
```

Completed steps are tracked in:

```text
outputs/<dataset-name>/.plk_state.json
```

Re-running the pipeline skips completed steps unless `--force` is used.

## App Run Behavior

The browser app treats step checkboxes as active/deactive pipeline membership.
All non-optional steps are active by default; optional steps such as
`UpscaleStep` stay inactive until checked. A normal app run starts at the first
pending active step and continues through later active steps in pipeline order,
skipping active steps already marked done. With force enabled, the app reruns the
active pipeline from the beginning.

Each step's substeps run in their canonical order inside the step. If a step or
substep fails by raising an error, that parent step is not marked done and the
app stops before downstream steps. Deactivating a required prerequisite is valid
only when that prerequisite is already satisfied in the selected output state.

## CLI Commands

`plk run`

Runs the full pipeline defined by a project config.

```bash
plk run -i /path/to/images -p example -t my_trigger
```

Important options:

- `--input`, `-i`: source dataset folder.
- `--output`, `-o`: output folder. Defaults to `outputs/<input-name>`.
- `--project`, `-p`: project config name. Defaults to the input folder name.
- `--token`, `-t`: concept token or trigger word. Omit for style training.
- `--force`: re-run all steps even if marked complete.

`plk step`

Runs a single step using the selected project's step config.

```bash
plk step -s CaptionStep -p example -i /path/to/images -o outputs/example -t my_trigger
plk step -s s5 -p example -i /path/to/images -o outputs/example -t my_trigger
```

Step aliases are `s0` through `s8` in pipeline order. `s0` imports the source
images; existing `s1` through `s8` aliases keep their historical meanings.

`plk projects`

Lists project configs discovered in `configs/projects/`.

`plk networks`

Lists network profiles discovered in `configs/networks/`.

`plk network-types`

Lists supported adapter network types: `lora`, `lokr`, and `dora`.

## Pipeline Stages

Pipeline stages are configured in `configs/projects/<name>.yaml`. The default
example pipeline has nine stages.

| Step | Type | Purpose | Main outputs |
| --- | --- | --- | --- |
| 0 | `ImportStep` | Copies source images into the working dataset. | Working `dataset/`, `ImportStep_report.json` |
| 1 | `QualityGateStep` | Scores imported images for size, blur, noise, JPEG artifacts, and watermark likelihood. Supports manual review. | Updated `dataset/`, `QualityGateStep_report.json` |
| 2 | `CurateStep` | Removes perceptual-hash duplicates and creates CLIP coverage plots. | Updated `dataset/`, coverage image, `CurateStep_report.json` |
| 3 | `UpscaleStep` | Upscales images below the target minimum side with the configured algorithm; unavailable algorithms warn and skip. | Updated images, `UpscaleStep_report.json` |
| 4 | `CaptionStep` | Opens bbox annotation UI, captions with Qwen VL, enforces concept token when supplied, and writes `.txt` sidecars. | Caption sidecars, `CaptionStep_report.json` |
| 5 | `VaeGateStep` | Reconstructs images through the target VAE and flags high-frequency loss outliers. | Updated `dataset/`, `VaeGateStep_report.json` |
| 6 | `AuditStep` | Verifies image-caption pairing, corrupt files, caption length, and minimum resolution. | `AuditStep_report.json` |
| 7 | `ConfigGenStep` | Builds ai-toolkit training YAML from dataset stats, project settings, and network profile defaults. | `run_config.yaml`, `ConfigGenStep_report.json` |
| 8 | `BucketDryRunStep` | Simulates bucket assignment and flags thin buckets before training. | Bucket report, optional `cache_info.json` |

Ordering rules are enforced when project configs load. Each step after
`ImportStep` requires the previous step to appear earlier in the pipeline, and
duplicate step types are rejected. Legacy configs that start with
`QualityGateStep` are loaded with `ImportStep` inserted in memory.

## Configuration Model

PrepareLoraKit separates project configuration from network configuration.

Project configs live in:

```text
configs/projects/
```

A project config chooses:

- the project name,
- the base network profile,
- an optional adapter type override,
- the ordered list of pipeline steps,
- step-specific settings.

Example:

```yaml
name: example
network: flux-klein-9b
network_type: dora

pipeline:
  - type: ImportStep
  - type: QualityGateStep
  - type: CurateStep
  - type: UpscaleStep
  - type: CaptionStep
  - type: VaeGateStep
  - type: AuditStep
  - type: ConfigGenStep
  - type: BucketDryRunStep
```

Network profiles live in:

```text
configs/networks/
```

A network profile describes the base model and its training defaults:

- display name,
- VAE model id,
- resolution buckets,
- recommended learning-rate and rank ranges,
- ai-toolkit `model`, `network`, `train`, `save`, and `sample` template blocks,
- training resolutions used when generating `run_config.yaml`.

The adapter network block is parsed through `prepare_lora_kit.networks.config`.
Supported adapter types are defined in `prepare_lora_kit.networks.net_types`.

## Output Layout

A typical completed run looks like:

```text
outputs/<dataset-name>/
  .plk_state.json
  dataset/
    image_001.png
    image_001.txt
    image_002.png
    image_002.txt
  reports/
    ImportStep_report.json
    QualityGateStep_report.json
    CurateStep_report.json
    coverage_pca.png
    UpscaleStep_report.json
    CaptionStep_report.json
    VaeGateStep_report.json
    AuditStep_report.json
    ConfigGenStep_report.json
    BucketDryRunStep_report.json
  run_config.yaml
```

`run_config.yaml` is the main handoff artifact for training.

## Important Runtime Dependencies

Install the cross-platform core (the minimum to run the default pipeline):

```bash
python -m pip install -r requirements.txt
```

The requirements are organized under `requirements/`:

- `requirements/base.txt` — core/minimum, cross-platform. The root
  `requirements.txt` is a thin shim that pulls this in.
- `requirements/seedvr2.txt` — optional SeedVR2 upscaling runtime.
- `requirements/seedvr2-windows.txt` / `requirements/seedvr2-linux.txt` —
  SeedVR2 plus OS-specific GPU acceleration extras.

The core depends on image processing, ML, and CLI libraries, including:

- Pillow, OpenCV, NumPy, scikit-image, scikit-learn, imagehash
- PyTorch, torchvision, transformers, accelerate, diffusers
- open_clip_torch, umap-learn, matplotlib
- Click, Rich, PyYAML
- easygui for fallback manual review flows
- bitsandbytes for optional 4-bit or 8-bit VLM quantization

`torch`/`torchvision` are pinned loosely; install a CUDA-specific build first
(see `--index-url` on https://pytorch.org) if the default wheel does not match
your GPU.

SeedVR2 upscaling is optional and uses the pinned submodule at
`third_party/seedvr2`. Before using `upscale_model: seedvr2`, install the
SeedVR2 extras for your OS and the submodule itself:

```bash
git submodule update --init --recursive third_party/seedvr2
python -m pip install -r requirements/seedvr2-windows.txt   # or seedvr2-linux.txt
python -m pip install -e third_party/seedvr2
```

PLK runs SeedVR2's standalone `inference_cli.py` inside an isolated Step 3 worker
process and does not import ComfyUI nodes into the main app process. All Step 3
upscale candidates are sent through one worker process so SeedVR2 can cache its
DiT and VAE models across the image loop. SeedVR2 models are downloaded into
`~/.cache/prepare_lora_kit/seedvr2` by default, configurable with
`seedvr2_model_dir`.

Select a supported DiT checkpoint with `seedvr2_dit_model`. Leaving the field
out, setting it to `null`, or leaving the YAML value empty uses the default
`seedvr2_ema_3b_fp8_e4m3fn.safetensors`.

```yaml
upscale_model: seedvr2
seedvr2_dit_model: seedvr2_ema_7b_fp8_e4m3fn_mixed_block35_fp16.safetensors
seedvr2_model_residency: auto  # auto | gpu | cpu
```

Supported SeedVR2 DiT models:

| Model | Size | Precision / quantization | Format | Variant | Label |
| --- | --- | --- | --- | --- | --- |
| `seedvr2_ema_3b_fp8_e4m3fn.safetensors` | 3B | fp8 e4m3fn | safetensors | base | default |
| `seedvr2_ema_3b_fp16.safetensors` | 3B | fp16 | safetensors | base | 3B quality |
| `seedvr2_ema_3b-Q4_K_M.gguf` | 3B | Q4_K_M | gguf | base | lower VRAM |
| `seedvr2_ema_3b-Q8_0.gguf` | 3B | Q8_0 | gguf | base | balanced GGUF |
| `seedvr2_ema_7b_fp8_e4m3fn_mixed_block35_fp16.safetensors` | 7B | fp8 e4m3fn mixed block35 fp16 | safetensors | base | higher quality |
| `seedvr2_ema_7b_fp16.safetensors` | 7B | fp16 | safetensors | base | highest quality |
| `seedvr2_ema_7b-Q4_K_M.gguf` | 7B | Q4_K_M | gguf | base | lower VRAM 7B |
| `seedvr2_ema_7b_sharp_fp8_e4m3fn_mixed_block35_fp16.safetensors` | 7B | fp8 e4m3fn mixed block35 fp16 | safetensors | sharp | sharp |
| `seedvr2_ema_7b_sharp_fp16.safetensors` | 7B | fp16 | safetensors | sharp | sharp highest quality |
| `seedvr2_ema_7b_sharp-Q4_K_M.gguf` | 7B | Q4_K_M | gguf | sharp | sharp lower VRAM |

For a 20-24 GB 7B path, start with
`seedvr2_ema_7b_fp8_e4m3fn_mixed_block35_fp16.safetensors`. Unknown filenames
emit a warning but are still accepted so local or experimental checkpoints can
be used.

If the submodule, SeedVR2 runtime dependencies, or SeedVR2 models are not
available, `upscale_model: seedvr2` skips upscale candidates with a report
reason. It does not fall back to Lanczos; use `upscale_model: lanczos`
explicitly when you want that algorithm.

`seedvr2_model_residency` controls where cached SeedVR2 models rest between
images. `auto` keeps models on GPU only when a conservative VRAM check suggests
it is safe; otherwise it caches with CPU offload. Use `gpu` for maximum speed on
high-VRAM systems, or `cpu` for lower peak VRAM.

## Extension Points

Add a new project preset:

1. Copy `configs/projects/example.yaml`.
2. Rename it to `configs/projects/<name>.yaml`.
3. Set `name: <name>`.
4. Adjust the pipeline and step settings.
5. Run with `plk run -i <dataset> -p <name>`.

Add a new network profile:

1. Add a YAML file under `configs/networks/`.
2. Match the schema in `prepare_lora_kit.networks.base.NetworkProfile`.
3. Include a `config_template` compatible with ai-toolkit.
4. Confirm discovery with `plk networks`.

Add a new pipeline step:

1. Add a step config dataclass under `prepare_lora_kit/project/configs/`.
2. Register it in `STEP_TYPE_MAP` in `prepare_lora_kit/project/steps.py`.
3. Implement the step module under `prepare_lora_kit/steps/`.
4. Add an invoke adapter in `prepare_lora_kit/invoke.py`.
5. Add any ordering rules to `STEP_PREREQUISITES`.

## Development Notes

Run tests with:

```bash
python3 -m pytest
```

The repository currently contains focused tests for pipeline behavior and
network configuration. The CLI is intentionally thin: command modules load
project and network config, then delegate execution to the pipeline orchestrator
and step invoke adapters.
