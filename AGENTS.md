# Repository Guidelines

## Project Structure & Module Organization

Projects are folders under `~/.prepare_lora_kit/projects/<name>/` — one
`index.yaml` plus one `<step>.yaml` per pipeline step; see
`docs/project-config.md`.

## Build, Test, and Development Commands

- `python -m pip install -e .`: installs the package (`prepare-lora-kit`), its core
  runtime dependencies, and registers `plk`. Dependencies are declared only in
  `pyproject.toml`; the files under `requirements/` are thin `-e .[extra]` shims.
  Add SeedVR2 with `pip install -e ".[seedvr2-accel]"` (or `.[seedvr2]` without
  GPU acceleration).
- `python main.py run -i /path/to/images -p my-project -t token`: runs the full
  local pipeline from the repo checkout.
- `uv sync` (or `python -m pip install --group dev`, pip 25.1+): installs the dev
  tooling (`ruff`, `pytest`, `pip-audit`) from the `dev` dependency group;
  `uv run` includes it by default.
- `pip-audit --skip-editable`: checks the active environment's installed packages
  for known vulnerabilities (installed with the `dev` group).

The repo may be shared between Windows and a Linux sandbox. `.venv` belongs to
Windows: any `uv run`/`uv sync` on Linux that resolves to `.venv` deletes it as
an incompatible environment. On Linux, point uv at its own environment **before
running any uv project command** (the mount may also lack symlink support):

```bash
export UV_PROJECT_ENVIRONMENT=.venv-linux   # relative to the project root
export UV_LINK_MODE=copy
uv sync                                     # then: uv run pytest / ruff / pip-audit
```

The `.venv-linux/` directory is machine-local and ignored by Git.

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

CSS conventions for the browser UI live in `prepare_lora_kit_ui/static/AGENTS.md`.

Keep `prepare_lora_kit_ui/static/core/api.js` JSDoc in sync with the pywebview
bridge whenever `prepare_lora_kit_ui/bridge.py`, UI bridge payloads, or frontend
API call sites change. Update `pyproject.toml` (core deps in `[project].dependencies`, optional
runtimes such as SeedVR2 in `[project.optional-dependencies]`) whenever adding,
removing, or changing runtime dependencies.

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
screenshots when modifying `prepare_lora_kit_ui/static/`.

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

<!-- bubble-tracks:start -->
## bubble-tracks (fog-of-war planning)

This repo plans work as linear tracks of task bubbles in `.bubble-tracks/` (one `.json` per track; `.bubble-tracks/current` names the active one).
Manage it only through the CLI, never by hand-editing the JSON:

    node ".agents/skills/bubble/scripts/cli/bubble.js" show | switch <name> | tracks | fork [N] <name> | diverge [N] <name> | init <title>
                   | add <title> | add ? | insert at N <title|?> | remove N[:M]
                   | move N[:M] to M | rename N <title> | title <text> | hint N <text> | fog [N[:M]] [TYPE]
                   | type [N] <TYPE> | fill [N] <title> | done

Full instructions: `.agents/skills/bubble/SKILL.md`.

Rules:
- Before editing project files, run `node ".agents/skills/bubble/scripts/cli/bubble.js" show`. If it exits 3, the active bubble is fog, so do not edit.
- At fog, never plan it yourself. Ask the human to classify it (known-known, known-unknown, unknown-known, unknown-unknown) and wait for their content before running `fill`.
- When the active bubble is a known task, read its hint, implement it, then run `done`.
- Keep each track to one domain. If the human asks for something that doesn't belong to the active bubble, don't `add` it: run `fork <name>` if it builds on the bubble (the bubble waits for it), or `diverge <name>` if it goes a different direction (nothing waits). Ask the human first (suggest one: fork / diverge / keep here), run it only after they pick, then treat the new track as fresh: ask, sketch, classify all fog.
- `bubble switch <name>` resumes a track (read all bubbles and hints, then continue at the active one) or creates it. Apply it right away without asking why. If you see a better name (e.g. `single commit` -> `single-commit`), use it and say so in one line.
- After sketching a track, always list every fog bubble by number and ask the human to answer each one as `N: <their content>` (then `fill`) or `N:kk|ku|uk|uu` (then `type`).
- When the chat gets long, save `handoff <note>` (what's half done, the decisions made, the next step) and suggest a fresh chat with `bubble switch <name>`.
- After `done`, stop (⏸): show the track and wait for the human before starting the next bubble.
- When the human writes `bubble <command>`, run exactly that command through the CLI and show the result.
- After every change, show the user the rendered track line.
<!-- bubble-tracks:end -->
