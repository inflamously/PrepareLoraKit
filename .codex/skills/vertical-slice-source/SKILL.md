---
name: vertical-slice-source
description: Split an existing source feature or UI step into a vertical-slice folder structure while preserving behavior. Use when Codex is asked to break up a large feature module, page, step, or single-file implementation into focused entrypoint, component, utility, formatter, constant, or state modules; especially for JavaScript/TypeScript frontend code and repo-local static UI modules.
---

# Vertical Slice Source

Use this skill to refactor a feature in place into small modules organized around the feature itself. Keep the public entry point stable unless the user explicitly asks for a broader API change.

## Workflow

1. Inspect the target folder and all importers before editing.
   - Find files under the target feature directory.
   - Search for imports of the current entry point and exported symbols.
   - Read nearby feature folders for local structure and naming conventions.

2. Identify natural boundaries from the existing code.
   - Keep orchestration, lifecycle, API calls, and submission flow in the entry point.
   - Move view rendering or DOM/widget construction into `components/`.
   - Move decisions, constants, normalization, formatting, and pure helpers into `utils/`.
   - Preserve CSS filenames and selectors unless the split requires stylesheet ownership changes.

3. Split conservatively.
   - Prefer one module per real responsibility, not one module per tiny function.
   - Export only what another module needs.
   - Keep relative imports simple and consistent with sibling features.
   - Do not rename externally imported entry files unless every importer is updated.

4. Preserve behavior during the move.
   - Move code first, then wire imports.
   - Keep data shapes, event semantics, DOM class names, IDs, ARIA attributes, and submission payloads unchanged.
   - Avoid opportunistic redesign, styling changes, or behavioral cleanup unless required to make the split correct.

5. Validate the module graph and existing behavior.
   - Run syntax checks for changed JS/TS modules when available.
   - Import the public entry point directly when the runtime supports ES modules.
   - Run the narrowest relevant tests first, then broader UI or package tests if cheap.
   - Check `git status --short` and summarize only files intentionally changed.

## JavaScript UI Pattern

For a single feature entry file such as `feature.js`, prefer this shape when it matches the code:

```text
feature/
├── feature.js          # public entry point and orchestration
├── feature.css         # existing styles, unchanged unless needed
├── components/
│   ├── card.js         # repeated item/card rendering
│   ├── detail.js       # selected item/detail panel rendering
│   └── modal.js        # modal/page shell construction
└── utils/
    ├── decisions.js    # options and normalization
    ├── format.js       # display formatting
    └── views.js        # view constants and selection helpers
```

Adjust names to the feature vocabulary already present in the repo.

## Completion Criteria

Finish with a concise summary that names the new structure, confirms the public entry point, and lists validation commands run. If tests cannot be run, state exactly why.
