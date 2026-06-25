---
name: trace-source-usage
description: Trace how a given file, source path, resource path, module, class, function, symbol, route, static asset, or configuration item is used in a codebase. Use when the user asks where something is used, when it runs, who calls it, whether it is dead code, what paths trigger it, or wants an easy-to-read usage map from a concrete path or symbol.
---

# Trace Source Usage

## Goal

Answer "when is this used and where is it used?" from source evidence, not memory. Produce a concise, easy-to-read map that separates direct references from runtime execution paths and notes situations where the target is not used.

## Workflow

1. Resolve the target.
   - Check whether the exact path exists.
   - If it does not, search nearby names and report likely typos or renames before continuing.
   - Identify whether the target is a file, symbol, resource, config key, route, or generated artifact.

2. Read the target first.
   - Identify public entry points, private helpers, exports, side effects, and fallback behavior.
   - Note names worth searching: filename stem, exported functions/classes, string IDs, route names, config keys, event names, CSS classes, and asset URLs.

3. Search broadly, then narrow.
   - Prefer `rg` and `rg --files`.
   - Search exact path fragments, module names, import paths, exported symbols, and user-facing identifiers.
   - Include tests and config files unless the user asks only for production code.
   - For frontend/static assets, search HTML, JS/TS, CSS, template files, build config, manifest files, and backend routes that serve assets.

4. Build the usage chain.
   - Start with direct references: imports, calls, includes, route registrations, config references, or asset links.
   - Walk outward to the parent workflow: CLI command, API endpoint, UI action, scheduler, pipeline step, test fixture, build process, or application startup.
   - Distinguish "referenced by code" from "actually reached at runtime".

5. Identify gates and alternatives.
   - Record conditions that must be true: feature flags, enabled substeps, config values, file existence, permissions, UI mode, command options, environment variables, or dependency availability.
   - Record bypasses: alternate providers, mocks, disabled substeps, cached outputs, existing sidecars, frontend-only replacements, or fallback behavior.

6. Verify the conclusion.
   - Use line-numbered reads (`nl -ba ... | sed -n`) for files cited in the final answer.
   - If there are no references, say that directly and mention what was searched.
   - Do not claim dead code unless import/export aliases, dynamic loading, config strings, package entry points, and tests were checked.

## Recommended Commands

Use these as starting points, adapting names to the repo:

```bash
rg --files | rg 'target-name|nearby-name'
rg -n 'exact_symbol|module_name|file_stem|user_facing_id' .
rg -n 'target/path|target\\.ext|route-name|config_key' .
nl -ba path/to/file | sed -n '1,220p'
```

For Python modules, also check package exports and entry points:

```bash
rg -n 'from .* import|import .*|__all__|entry_points|console_scripts|click\\.command|argparse' .
```

For frontend resources, also check API bridges and static references:

```bash
rg -n 'asset_name|componentName|event-name|api_method|route_path|css-class' .
```

## Answer Shape

Keep the final answer easy to scan. Prefer this structure:

1. **Target**: State the resolved file/symbol. If the user supplied a typo, mention the exact correction.
2. **What it is**: One short paragraph explaining the target's role.
3. **Main use path**: Show the call/resource chain as arrows, from user-facing trigger to target.
4. **When it is used**: Bullet the runtime conditions.
5. **Where it is used**: Bullet direct references with clickable file links and line numbers.
6. **When it is not used**: Bullet bypasses, alternatives, skipped modes, mocks, or caches.
7. **Tests/coverage**: Mention relevant tests when useful.

Example chain format:

```text
CLI command
-> pipeline runner
-> step invoker
-> step.run(...)
-> workflow helper
-> interaction provider
-> target function
```

## Precision Rules

- Cite local files with clickable absolute links when answering.
- Avoid dumping every search hit; group hits by role.
- Call out uncertainty explicitly when dynamic imports, reflection, plugin loading, generated code, or external consumers may exist.
- If the target has both CLI and UI paths, split them. State which path uses the target and which path uses an alternative.
- If tests are the only references, say "I found test-only usage" rather than implying production use.
