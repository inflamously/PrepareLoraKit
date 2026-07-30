# Project configuration

A project is a **folder**, not a file:

```text
~/.prepare_lora_kit/projects/<name>/
├── index.yaml               identity, and which steps run
├── import.yaml              one file per step, holding that step's settings
├── quality_gate.yaml
├── curate.yaml
├── upscale.yaml
├── caption_bbox.yaml
├── caption_verifier.yaml
├── vae_gate.yaml
├── audit.yaml
├── bucket_pools_check.yaml
└── export.yaml
```

It lives outside the checkout for the same reason
[`settings.yaml`](settings.md) does: it survives a re-clone, is shared by every
working copy, and a dataset path like `D:\datasets\portraits` is machine-specific
user data that has no business in a repo.

Create one from the UI's **New project** button, or by running `plk run -i
<folder>` and accepting the prompt. `plk projects` lists what you have.

## `index.yaml`

```yaml
name: my-portraits
input_dir: D:/datasets/portraits
output_dir: null                       # omit or null → outputs/<input folder name>

pipeline:
  - {step: import, enabled: true}
  - {step: quality_gate, enabled: true}
  - {step: curate, enabled: true}
  - {step: upscale, enabled: false}    # parked: skipped, upscale.yaml is kept
  - {step: caption_bbox, enabled: true}
  - {step: caption_verifier, enabled: true}
  - {step: vae_gate, enabled: true}
  - {step: audit, enabled: true}
  - {step: bucket_pools_check, enabled: true}
  - {step: export, enabled: true}
```

`pipeline:` is the table of contents. It decides **which steps run and in what
order**, and each entry names a sibling `<step>.yaml`.

- `enabled: false` **parks** a step. It is skipped, but its file — and every
  setting you tuned in it — stays on disk. Flip it back to `true` to get the step
  and its settings back exactly as they were.
- A `<step>.yaml` **not listed** in `pipeline:` is ignored. So is any other file
  in the folder; the index drives the read, never a directory scan.
- A step **listed with no file** runs on built-in defaults, and says so on load.
  That means an `index.yaml` on its own is a valid, minimal project.
- The order must follow the canonical pipeline order below. Reordering is
  rejected on load rather than silently corrected, so the file never lies about
  what will run.

Steps are only constrained by their prerequisites: disabling `quality_gate` while
`curate` is on is an error (and says so), but disabling a step nothing depends on
— even a non-optional one like `bucket_pools_check` — is fine.

## Step names

The file name is the step's **slug**. Reports and run state use the step **type**,
so this is the table to reach for when `reports/CaptionBboxStep_report.json`
sends you looking for the file to edit:

| File | Step type | Optional |
| --- | --- | --- |
| `import.yaml` | `ImportStep` | |
| `quality_gate.yaml` | `QualityGateStep` | |
| `curate.yaml` | `CurateStep` | |
| `upscale.yaml` | `UpscaleStep` | ✓ |
| `caption_bbox.yaml` | `CaptionBboxStep` | |
| `caption_verifier.yaml` | `CaptionVerifierStep` | ✓ |
| `vae_gate.yaml` | `VaeGateStep` | |
| `audit.yaml` | `AuditStep` | |
| `bucket_pools_check.yaml` | `BucketPoolsCheckStep` | |
| `export.yaml` | `ExportStep` | ✓ |

`plk step -s` accepts either spelling: `plk step -s caption_bbox` and
`plk step -s CaptionBboxStep` are the same command.

**`enabled` and `optional` are different things.** `enabled` (in `index.yaml`) is
pipeline membership — whether the step runs at all. `optional` is a fixed
property of the step that only decides whether its checkbox starts ticked in the
UI, and whether it counts toward a project showing as *completed* in the library.

## Step files

Each one holds its `substeps:` — the ordered units inside that step — followed by
its settings, flat:

```yaml
# caption_bbox.yaml
substeps:
  - {id: annotate_regions, enabled: true}
  - {id: caption_images, enabled: true}
  - {id: validate_captions, enabled: true}
caption_model_id: Qwen/Qwen2-VL-7B-Instruct
caption_model_task: auto
vram_tier: auto                # auto | low (≤16GB) | mid (≤24GB) | high | max
max_new_tokens: 200
spot_check_pct: 0.1
```

Settings that are lists of short records stay on one line each, which is most of
the point of splitting the config up:

```yaml
# quality_gate.yaml
substeps:
  - {id: score_images, enabled: true}
  - {id: review_decisions, enabled: true}
scorers:
  - {name: min_side, enabled: true, op: lt, threshold: 1024.0}
  - {name: blur, enabled: true, op: lt, threshold: 100.0, borderline: 150.0}
  - {name: noise, enabled: true, op: gt, threshold: 25.0}
manual_review: true
auto_only: false               # true = skip all manual review
manual_all: false              # true = review every image
```

Omitting a setting means "use the default", and omitting a substep means "use its
default enabled state" — you never have to write out a whole file to change one
value.

### Where it is safe to write comments

**Step files are written once, when the project is created, and only ever read
afterwards.** Comments and formatting you add to them are permanent, and survive
renames and duplication byte-for-byte.

`index.yaml` is different: the app rewrites it when you rename a project or open
its folder from the UI, so comments there are regenerated away.

## Recipes

**Change a setting.** Edit the relevant `<step>.yaml`. Nothing else needs to know.

**Park a step.** Set `enabled: false` on its line in `index.yaml`. Its file stays
put. ⚠️ Note that run state is keyed per step: if a step was already `done` before
you parked it, re-enabling it later will find it still marked done and skip it.
Use `--force` on that step to actually re-run it.

**Start over on one step.** Delete its `<step>.yaml`. It will run on built-in
defaults and tell you it did.

**Copy a tuned project.** Duplicate it from the library grid; every step file is
copied verbatim.

## Related

- [`docs/run-state-and-reports.md`](run-state-and-reports.md) — what `done`,
  `skipped` and `pending` mean on a step, and why the badge and
  `reports/<StepType>_report.json` always agree.
- [`docs/settings.md`](settings.md) — app-wide settings, and which of them seed a
  *new* project's files at creation time. Changing a global later never rewrites
  an existing project; its own files are the only thing that decides how it runs.
