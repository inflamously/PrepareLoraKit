---
name: audit-complexity-debt
description: Audit a source repository for complexity technical debt. Use when the user asks to list files that exceed a line-count threshold, have too many intents or use-cases in one file, are hard to read, should be split, or should be documented as refactor/maintainability debt.
---

# Audit Complexity Debt

## Overview

Find files that are likely refactor candidates because they are large, mixed-responsibility, broad test suites, duplicated style bundles, vendored integration hotspots, or otherwise difficult to read safely.

Prefer evidence from the local repository over generic advice. Use line counts to find candidates, then inspect enough source to describe the actual responsibilities in one concise sentence.

## Workflow

1. Scan source files with `rg --files` or the helper script.
2. Exclude noisy dependency/build folders unless the user explicitly asks to include them:
   `.git`, `.venv`, `venv`, `env`, `node_modules`, `dist`, `build`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `__pycache__`.
3. Treat checked-in `third_party` or `vendor` code as separate from first-party code. Include it only when it is maintained in-repo or materially affects the project.
4. Prioritize files over roughly 300 LoC, then add below-threshold files only when inspection shows high intent density.
5. Inspect each candidate before reporting it. Do not rely on LoC alone.
6. Return a compact table unless the user requests a narrative.
7. Store this table locally as a markdown resource under docs (complexity-technical-debt.md).

Use this helper for the first pass:

```bash
python3 .codex/skills/audit-complexity-debt/scripts/complexity_scan.py --root . --top 80
```

If the repository does not have this skill path available, fall back to:

```bash
find . \
  -path './.git' -prune -o \
  -path './.venv' -prune -o \
  -path './node_modules' -prune -o \
  -type f \( -name '*.py' -o -name '*.js' -o -name '*.ts' -o -name '*.tsx' -o -name '*.css' -o -name '*.html' \) \
  -print0 | xargs -0 wc -l | sort -nr | head -80
```

## What To Flag

Flag a file when one or more of these apply:

- It is over the requested threshold, defaulting to about 300 LoC.
- It mixes orchestration, domain logic, IO, UI payload shaping, validation, mock/runtime fixtures, and reporting in one module.
- It is a test file covering several unrelated behaviors that would be clearer as focused modules.
- It is a stylesheet that combines tokens, reset, layout, component styling, and page-specific behavior.
- It is vendored or third-party code that is checked in and large enough to affect local maintenance.
- It is below threshold but acts as a registry plus normalization plus compatibility/migration plus payload builder.

Avoid flagging a large file as debt when inspection shows it is generated, purely declarative data, a coherent single-purpose artifact, or outside the user's scope.

## Output

For quick inventory requests, use exactly this shape:

```markdown
|filepath|description|
|path/to/file.py|312 LoC; concise reason based on inspected responsibilities.|
```

When writing to a document, include a short scope note and a markdown table:

```markdown
# Complexity Technical Debt

This list highlights files that exceed roughly 300 lines of code, carry too many responsibilities in one place, or are otherwise harder than necessary to read and modify.

| Filepath | Description |
| --- | --- |
| `path/to/file.py` | 312 LoC; concise reason. |
```

Keep descriptions specific enough to guide a future split. Name the mixed intents rather than saying only "too large" or "complex."
