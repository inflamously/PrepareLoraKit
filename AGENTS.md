# Repository Guidelines

## Project Structure & Module Organization

PrepareLoraKit is a Python 3.10+ package with a Click CLI exposed as `plk`.
Core package code lives in `prepare_lora_kit/`. CLI entry points are in
`prepare_lora_kit/cli/`, pipeline orchestration is in `pipeline.py`, project and
network config models are in `project/` and `networks/`, and pipeline stages are
split under `steps/s1_source` through `steps/s8_bucket`. The browser UI assets
live in `prepare_lora_kit/ui/static/`. YAML examples and network profiles live
under `configs/`. Tests are in `tests/` and currently use pytest-style functions.

## Build, Test, and Development Commands

- `python -m pip install -r requirements.txt`: installs runtime dependencies.
- `python -m pip install -e .`: installs the package locally and registers `plk`.
- `python main.py --help` or `plk --help`: lists available CLI commands.
- `python main.py run -i /path/to/images -p example -t token`: runs the full
  local pipeline from the repo checkout.
- `pytest`: runs the test suite in `tests/`.
- `pytest tests/project/test_config.py`: runs one focused test module.

## Coding Style & Naming Conventions

Use idiomatic Python with 4-space indentation, clear function names, and small
modules grouped by domain. Keep step implementations in their existing numbered
stage packages and name new step classes with the `*Step` suffix, for example
`CaptionStep`. Tests should be named `test_<behavior>` and organized as
`tests/<domain>/test_<area>.py`. Prefer `pathlib.Path` for filesystem paths and
structured YAML parsing over ad hoc string handling.

Keep `prepare_lora_kit/ui/static/core/api.js` JSDoc in sync with the pywebview
bridge whenever `prepare_lora_kit/ui/bridge.py`, UI bridge payloads, or frontend
API call sites change. Update `requirements.txt` whenever adding, removing, or
changing runtime dependencies.

## Testing Guidelines

Add or update tests whenever changing project config parsing, pipeline ordering,
CLI behavior, or UI bridge payloads. Use `tmp_path`, `monkeypatch`, and mocks to
avoid touching real datasets, model caches, or network services. Keep tests fast
by mocking ML-heavy components such as model loading, captioning, upscaling, and
VAE evaluation.

## Commit & Pull Request Guidelines

Recent history uses short conventional-style prefixes such as `feat:`, `fix:`,
and `refactor:`. Follow that style with an imperative summary, for example
`fix: preserve project input dir`. Pull requests should describe the user-facing
change, list tests run, call out config or dependency changes, and include UI
screenshots when modifying `prepare_lora_kit/ui/static/`.

## Security & Configuration Tips

- Do not commit generated datasets, reports, model weights, or local `outputs/`
content. Keep machine-specific paths in local project YAML files and document any
required environment variables, such as `SEEDVR_PATH`, when adding optional
runtime integrations.
- Avoid installation of runtime in sandboxes, if .venv present keep it intact.
