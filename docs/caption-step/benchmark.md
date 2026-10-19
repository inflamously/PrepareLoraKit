# Caption benchmark

Part of the [Caption Step reference](README.md).

`plk caption-bench` captions a fixed set of images with one or more **variants** (caption
config overrides), stores every run, and shows the runs side by side with word changes against
a baseline highlighted. Use it to measure a prompt or setting change before it reaches a real
dataset. Code: `prepare_lora_kit/caption_bench/`, CLI: `prepare_lora_kit/cli/bench.py`.

## Quick start

```bash
plk caption-bench init food -t krustekrabbe          # creates ~/.prepare_lora_kit/bench/food
                                                     # and opens it in the file manager
plk caption-bench init food --images path/to/dataset # same, copying a dataset's images
# drop images into images/, optionally add notes/boxes in bench.yaml, then:
plk caption-bench run food
plk caption-bench view food
```

`SUITE` is everywhere either a folder path or a **bare name**, which resolves to
`~/.prepare_lora_kit/bench/<name>` (unless a folder of that name exists in the current
directory). `init` never overwrites an existing `bench.yaml`; `--no-open` skips opening the
folder, `--model` sets the caption model written to `defaults`, and `--images` skips region
crops (`plk_bbox__*`).

## Suite layout

A suite is any folder (keep it outside the repo; by default `~/.prepare_lora_kit/bench/<name>/`):

```
<suite>/
  bench.yaml
  images/…                 # used as the case list when bench.yaml has no `images`
  variants/<name>.yaml     # CaptionBboxConfig overrides, one file per variant
  runs/<run_id>.json       # written by `run`
```

```yaml
# bench.yaml
name: food
concept_token: krustekrabbe          # suite default; a case may override it or set null
defaults:                            # CaptionBboxConfig overrides applied to every variant
  caption_model_id: Qwen/Qwen3-VL-8B-Instruct
  vram_tier: low
images:
  - path: images/burger.png
    notes: invented food item, should be named krustekrabbe
    annotations:                     # same shape as the step's boxes sidecar
      - {label: sesame claws, x1: 0.1, y1: 0.1, x2: 0.4, y2: 0.4}
  - path: images/beach.png
    concept_token: null              # captioned in style mode
```

```yaml
# variants/single.yaml — any CaptionBboxConfig field; unknown keys are rejected
caption_strategy: single
```

Precedence: suite `defaults` < variant file < `--model`. The `current` variant always exists:
the suite defaults over today's built-in config. Record a `current` run **before** changing
prompts or captioning code, so you have a baseline to compare against.

## Commands

```bash
plk caption-bench init SUITE [-t TOKEN] [--model ID] [--images DIR] [--no-open]
plk caption-bench run SUITE                       # the `current` variant
plk caption-bench run SUITE -v current -v single  # several variants, one model load if shared
plk caption-bench run SUITE --model Qwen/Qwen3-VL-4B-Instruct
plk caption-bench run SUITE --mock                # no model: exercises the flow only
plk caption-bench runs SUITE                      # stored runs, oldest first
plk caption-bench view SUITE                      # Textual viewer (pip install -e ".[bench]")
plk caption-bench view SUITE --plain --trace      # print everything, no TUI
plk caption-bench view SUITE -r 20261012 -r focus -b 20261001   # choose runs/baseline
```

`view` shows the latest run of each variant by default, diffed against the oldest of those
(`--baseline` overrides). Run references accept a unique prefix of the run id. In the Textual
view, `↑/↓` pick an image, `t` toggles the pass trace, `o` opens the image, and `q` quits.

## What a run records

Per image: the final caption (cleaned exactly as the step writes it, via
`validation.clean_caption_for_mode`), the raw model output, the **pass trace** (observe facts,
compose draft, gap-fill raw output and kept phrases, from the `trace` hook in
`grounded.generate_grounded_caption`), the passes run, seconds, word count, and any error. A
failing image is recorded and the run continues. Per run: variant, the resolved config, model
metadata, and the git commit (`+dirty` if the work tree has uncommitted changes).

The runtime is built by `real.make_caption_runtime`, the same factory the step uses, so a
benchmark run captions with exactly the settings a project run would.
