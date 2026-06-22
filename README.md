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

Step aliases are `s1` through `s8` in pipeline order.

`plk projects`

Lists project configs discovered in `configs/projects/`.

`plk networks`

Lists network profiles discovered in `configs/networks/`.

`plk network-types`

Lists supported adapter network types: `lora`, `lokr`, and `dora`.

## Pipeline Stages

Pipeline stages are configured in `configs/projects/<name>.yaml`. The default
example pipeline has eight stages.

| Step | Type | Purpose | Main outputs |
| --- | --- | --- | --- |
| 1 | `QualityGateStep` | Scores source images for size, blur, noise, JPEG artifacts, and watermark likelihood. Supports manual review. | Working `dataset/`, `QualityGateStep_report.json` |
| 2 | `CurateStep` | Removes perceptual-hash duplicates, creates CLIP coverage plots, and flags occlusion or ambiguous images. | Updated `dataset/`, coverage image, `CurateStep_report.json` |
| 3 | `UpscaleStep` | Upscales images below the target minimum side with the configured algorithm; unavailable algorithms warn and skip. | Updated images, `UpscaleStep_report.json` |
| 4 | `VaeGateStep` | Reconstructs images through the target VAE and flags high-frequency loss outliers. | Updated `dataset/`, `VaeGateStep_report.json` |
| 5 | `CaptionStep` | Opens bbox annotation UI, captions with Qwen VL, enforces concept token when supplied, and writes `.txt` sidecars. | Caption sidecars, `CaptionStep_report.json` |
| 6 | `AuditStep` | Verifies image-caption pairing, corrupt files, caption length, and minimum resolution. | `AuditStep_report.json` |
| 7 | `ConfigGenStep` | Builds ai-toolkit training YAML from dataset stats, project settings, and network profile defaults. | `run_config.yaml`, `ConfigGenStep_report.json` |
| 8 | `BucketDryRunStep` | Simulates bucket assignment and flags thin buckets before training. | Bucket report, optional `cache_info.json` |

Ordering rules are enforced when project configs load:

- `AuditStep` requires `CaptionStep` earlier in the pipeline.
- `ConfigGenStep` requires `CaptionStep` earlier in the pipeline.
- `BucketDryRunStep` requires `ConfigGenStep` earlier in the pipeline.
- Duplicate step types are rejected.

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
  - type: QualityGateStep
  - type: CaptionStep
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
    QualityGateStep_report.json
    CurateStep_report.json
    coverage_pca.png
    UpscaleStep_report.json
    VaeGateStep_report.json
    CaptionStep_report.json
    AuditStep_report.json
    ConfigGenStep_report.json
    BucketDryRunStep_report.json
  run_config.yaml
```

`run_config.yaml` is the main handoff artifact for training.

## Important Runtime Dependencies

The project depends on image processing, ML, and CLI libraries listed in
`requirements.txt`, including:

- Pillow, OpenCV, NumPy, SciPy, scikit-image, scikit-learn, imagehash
- PyTorch, torchvision, transformers, accelerate, diffusers
- umap-learn, matplotlib, lpips
- Click, Rich, PyYAML
- easygui for fallback manual review flows
- bitsandbytes for optional 4-bit or 8-bit VLM quantization

SeedVR upscaling is optional. If `upscale_model: seedvr` is configured and
`SEEDVR_PATH` is unset, the upscale step warns and skips candidates. Use
`upscale_model: lanczos` explicitly when you want the Lanczos fallback algorithm.

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
2. Register it in `STEP_TYPE_MAP` in `prepare_lora_kit/project/base.py`.
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
