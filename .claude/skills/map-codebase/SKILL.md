---
name: map-codebase
description: Generate a deterministic, self-contained HTML code map of a codebase showing each file's classes and functions, outgoing imports with symbol names, and incoming referenced-by edges, plus a package-level meta map for navigation. Use when the user asks for a code map, an import or dependency map/chart/overview, a module graph, "how do these files connect", or help navigating an unfamiliar or messy codebase.
---

# Map Codebase

## Overview

Builds `docs/code-map.html` — a single self-contained page (no external requests, safe to
open via `file://` and to commit) mapping the whole codebase:

- **Sidebar tree** of all source files with a live filter over paths *and* definition names.
- **Per-file view** (`#f=<path>`, shareable): defined classes (with methods), functions and
  exported consts with line numbers; outgoing imports with the exact symbols imported;
  external imports split into stdlib / third-party / unresolved; and a **Referenced by**
  section listing every file that imports this one and which symbols it takes.
- **Meta map** (`#`): a package adjacency table (groups = top two path levels) with
  import/imported-by edge counts, each linking to a group view (`#g=<group>`).

Static analysis only: Python via `ast` (relative and absolute imports resolved, `from pkg
import name` disambiguated between submodule and symbol, `TYPE_CHECKING` imports tagged),
JS/ESM via regex (named/default/namespace/side-effect/dynamic imports, re-exports,
`export function|class|const`). Stdlib-only scripts; output is **deterministic** — same
code produces a byte-identical file, so diffs of the map are meaningful.

## Workflow

1. Build the map (exclude test trees if the user only wants production code):

   ```bash
   python3 .claude/skills/map-codebase/scripts/build_code_map.py \
     --root . --out docs/code-map.html --exclude tests --check
   ```

2. `--check` prints a resolution report (file counts, edge count, resolution rate,
   stdlib/third-party module counts) and exits non-zero if there are parse errors or
   unresolved-internal imports. Report any unresolved entries to the user — they are
   usually dead imports, optional dependencies, or dynamic imports.
3. Tell the user to open `docs/code-map.html` in a browser (no server needed).
4. Regenerate after refactors; because output is deterministic, `git diff` on the HTML
   shows exactly which edges/defs changed.

## Options

| Flag | Meaning |
| --- | --- |
| `--root PATH` | Repository root to scan (default `.`). |
| `--out PATH` | Output HTML (default `<root>/docs/code-map.html`). |
| `--include PREFIX` | Repeatable; scan only these repo-relative prefixes. |
| `--exclude NAME` | Repeatable; skip this directory name at any depth (adds to defaults). |
| `--check` | Print resolution report; exit 1 on parse errors / unresolved imports. |
| `--json` | Print the JSON model to stdout instead of writing HTML (for spot checks). |

Default excludes: all dot-directories plus `node_modules third_party vendor outputs dist
build venv env __pycache__`.

## Portability

Copy `.claude/skills/map-codebase/` into any project as-is. Python packages (directories
with `__init__.py`) and `.js`/`.mjs` files are auto-discovered from `--root`; nothing in
the scripts references this repository. Adjust `--exclude`/`--include` for
project-specific layouts.

## Limitations

- Static only: `importlib`/`__import__` and non-literal JS `import(expr)` are not traced.
- `__init__.py` re-exports resolve to the `__init__.py` itself (follow one more hop from
  its file view); namespace packages (no `__init__.py`) are not mapped.
- JS parsing is regex-based: no class-method extraction, TS/JSX unsupported, and comment
  stripping can be fooled by import-like text inside string literals.
- No call-graph: "Referenced by" means "imports this file", not "calls this function".

## Output

`docs/code-map.html` — self-contained, hash-routed (`#f=`/`#g=` links are shareable),
searchable, honors light/dark via `prefers-color-scheme`. Plus the `--check` report on
stdout when requested.
