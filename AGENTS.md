# Repository Guidelines

## Project Structure & Module Organization

PrepareLoraKit is a Python 3.10+ package with a Click CLI exposed as `plk`.
Core package code lives in `prepare_lora_kit/`. CLI entry points are in
`prepare_lora_kit/cli/`, pipeline orchestration is in `pipeline.py`, project
models are in `project/`, and dataset pipeline stages are split under named
packages such as `steps/import_step`, `steps/caption_bbox`, and
`steps/bucket_pools_check`. The browser UI assets live in
`prepare_lora_kit_ui/static/`. Projects are folders under
`~/.prepare_lora_kit/projects/<name>/` — one `index.yaml` plus one `<step>.yaml`
per pipeline step; see `docs/project-config.md`. Tests are in `tests/` and
currently use pytest-style functions.

## Build, Test, and Development Commands

- `python -m pip install -r requirements.txt`: installs the core runtime dependencies
  (a shim for `requirements/base.txt`). Add SeedVR2 with
  `pip install -r requirements/seedvr2-windows.txt` (or `-linux`).
- `python -m pip install -e .`: installs the package locally and registers `plk`.
- `python main.py --help` or `plk --help`: lists available CLI commands.
- `python main.py run -i /path/to/images -p my-project -t token`: runs the full
  local pipeline from the repo checkout.
- `pytest`: runs the test suite in `tests/`.
- `pytest tests/project/test_config.py`: runs one focused test module.
- `python -m pip install -r requirements/dev.txt`: installs the dev tooling
  (`ruff`, `pytest`) on top of the runtime deps.
- `ruff check .`: lints the repo. `ruff check --fix .` applies the safe fixes.

On Linux, keep an existing Windows `.venv` intact and create a separate local
environment. This workspace may be mounted without symlink support, so use an
uv-managed Python with copied venv files:

```bash
uv python install 3.12
mkdir -p .venv-linux/lib64
"$(uv python find 3.12)" -m venv --copies .venv-linux
uv pip install --python .venv-linux/bin/python --link-mode copy -r requirements/dev.txt
```

In a headless Linux environment without `libxcb.so.1`, replace the GUI OpenCV
wheel after installation:

```bash
uv pip uninstall --python .venv-linux/bin/python opencv-python
uv pip install --python .venv-linux/bin/python --link-mode copy opencv-python-headless
```

Run checks through `.venv-linux/bin/pytest` and `.venv-linux/bin/ruff`. The
`.venv-linux/` directory is machine-local and ignored by Git.

## Coding Style & Naming Conventions

Use idiomatic Python with 4-space indentation, clear function names, and small
modules grouped by domain. Keep step implementations in named stage packages and
name new step classes with the `*Step` suffix, for example `CaptionBboxStep`.
Prefer focused classes for non-trivial functions and use cases, especially when
logic coordinates multiple operations, dependencies, or mutable state. Avoid
long functions: keep functions small and single-purpose, and extract substantial
workflows into cohesive classes with clearly named methods.
Tests should be named `test_<behavior>` and organized as
`tests/<domain>/test_<area>.py`. Prefer `pathlib.Path` for filesystem paths and
structured YAML parsing over ad hoc string handling.

### Linting

`ruff check .` must be clean before a change is done — the full rule set lives in
`pyproject.toml` under `[tool.ruff.lint]`, and every `ignore` entry there carries
a comment explaining why. The line limit is 100.

The complexity rules are the point of the config, not incidental: a function over
**complexity 10 / 12 branches / 50 statements** is telling you it holds more than
one job. Fix it by extracting a named helper or a cohesive class, not by raising
the threshold or adding a `noqa`. There is deliberately no baseline ignore list —
the repo is at zero violations, so any new one belongs to the change that
introduced it.

Two rules are switched off for scope reasons rather than principle, and are the
natural next ratchet: `PLR0913`/`PLR0917` (too many arguments) currently has ~24
offenders, mostly step `run()` signatures and their callers. `T201` (`print`) is
off because the interactive `review.py` modules print to the console by design.

A `PostToolUse` hook in `.claude/settings.json` runs `.claude/hooks/ruff_check.py`
after any Python file is written, so violations surface immediately instead of at
review time. It no-ops silently when ruff is not installed.

### Scrolling and overflow (CSS)

A box that scrolls on one axis must state the other axis too. Omitting it is not
"no scrolling": when one axis is not `visible`, the other computes from `visible`
to `auto`, so a lone `overflow-y: auto` silently makes the box a horizontal
scroll container as well. Clamp the idle axis with the pair

```css
overflow-x: hidden;
overflow-x: clip;   /* engines below Chromium 90 / WebKitGTK 2.38 drop this */
```

`clip` rather than `hidden` because `hidden` still leaves a scroll container:
it only removes the scrollbar while the browser goes on scrolling the box on
focus and on `scrollIntoView`, stranding a pane offset with no way to scroll it
back. Make content fit *before* clamping an axis — clamping first only trades a
visible scrollbar for invisible clipping. `tests/ui/static/css_overflow.test.js`
enforces both halves of this and rejects the `overflow: auto` shorthand, so
intent is always written out. The rationale lives in
`prepare_lora_kit_ui/static/core/foundation.css`.

Keep `prepare_lora_kit_ui/static/core/api.js` JSDoc in sync with the pywebview
bridge whenever `prepare_lora_kit_ui/bridge.py`, UI bridge payloads, or frontend
API call sites change. Update the files under `requirements/` (core deps in
`base.txt`, SeedVR2 extras in `seedvr2*.txt`) whenever adding, removing, or
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
content. Machine-specific paths belong in app settings
(`~/.prepare_lora_kit/settings.yaml`, edited from the UI's Settings button — see
`docs/settings.md`), which lives outside the repo; a project YAML may still
override any of them. Document any required environment variables, such as
`SEEDVR_PATH`, when adding optional runtime integrations.
- Never store a Hugging Face token in this repo or in app settings. The app
reuses the token `hf auth login` writes, via `huggingface_hub.get_token()`.
- Avoid global runtime installation in sandboxes. Keep an existing `.venv`
  intact; when it is platform-incompatible, use the separate `.venv-linux`
  workflow documented above.
