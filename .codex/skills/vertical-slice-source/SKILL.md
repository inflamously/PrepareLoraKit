---
name: vertical-slice-source
description: Split an existing source feature, module, workflow, page, or large implementation into focused vertical-slice files while preserving behavior. Use when Codex is asked to break up source code by responsibility or intent in any language or framework, including frontend, backend, CLI, configuration, tests, or repo-local static assets.
---

# Vertical Slice Source

Use this skill to refactor source in place into smaller files organized around the feature, domain, or intent already present in the codebase. Keep the public entry point stable unless the user explicitly asks for a broader API change.

## Workflow

1. Inspect the target and all importers before editing.
   - Find files under the target feature or module directory.
   - Search for imports, entry points, registered routes/commands, exported symbols, tests, docs, and generated file maps that mention the current file.
   - Read nearby folders to learn local naming, packaging, and ownership conventions.

2. Confirm the slice location before moving code.
   - If the user already specified the layout, restate that assumption briefly and proceed.
   - Otherwise ask whether the split should live in the same folder as the current file, under a single domain or feature folder, under a shared/top-level concern folder, or in another structure they prefer.
   - Do not silently choose between same-folder, domain-folder, or shared-folder layouts when the request leaves that open.

3. Identify natural boundaries from the existing code.
   - Keep public entry points, orchestration, lifecycle, command/route registration, and outward-facing APIs stable.
   - Move cohesive responsibilities into focused modules, such as state, configuration, validation, parsing, formatting, rendering, adapters, persistence, transport, decisions, constants, fixtures, or tests.
   - Use names from the domain and surrounding code rather than generic names copied from another stack.
   - Preserve existing stylesheet, template, schema, and asset ownership unless the split requires changing it.

4. Split conservatively.
   - Prefer one module per real responsibility, not one module per tiny function.
   - Export only what another module needs.
   - Keep relative imports, package boundaries, initialization order, and dependency direction simple.
   - Leave compatibility shims or re-exports when current import paths are part of the local public surface.
   - Update docs, file maps, type declarations, config manifests, and bridge/API documentation when the moved code changes those surfaces.

5. Preserve behavior during the move.
   - Move code first, then wire imports.
   - Keep data shapes, event semantics, DOM selectors, IDs, route names, CLI names, config keys, payloads, exceptions, and side effects unchanged.
   - Avoid opportunistic cleanup, redesign, dependency changes, or behavior changes unless required to make the split correct.

6. Validate the module graph and existing behavior.
   - Run language-appropriate syntax, type, lint, import, or compile checks for changed files when available.
   - Import or execute the public entry point when the runtime supports a cheap smoke test.
   - Run the narrowest relevant tests first, then broader tests if cheap.
   - Check `git status --short` and summarize only files intentionally changed.

## Layout Guidance

Use the structure that matches the chosen ownership boundary and local conventions. Examples:

```text
feature-or-domain/
|-- entrypoint.ext      # public entry point, orchestration, compatibility exports
|-- state.ext           # domain state or state helpers, if this is a real concern
|-- validation.ext      # validation or normalization
|-- formatting.ext      # display or serialization formatting
|-- adapters/           # I/O, framework, transport, persistence, or bridge adapters
|-- components/         # UI or reusable composition units when the stack has them
`-- tests/              # focused tests if local test layout keeps them near code
```

```text
+shared-concern/
|-- index.ext           # shared public entry point
|-- domain-a.ext
|-- domain-b.ext
`-- domain-c.ext
```

Treat these as examples, not templates. For Python packages, respect package `__init__.py` exports and test layout. For JavaScript or TypeScript, respect ES module paths and bundler constraints. For CLI, backend, and configuration code, preserve registered names and external schemas.

## Completion Criteria

Finish with a concise summary that names the new structure, confirms the public entry point or compatibility path, and lists validation commands run. If tests cannot be run, state exactly why.
