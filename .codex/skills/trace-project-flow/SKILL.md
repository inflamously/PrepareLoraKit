---
name: trace-project-flow
description: Trace how a feature, UI behavior, API endpoint, CLI command, config key, event, file, module, class, function, asset, or runtime interaction works across a codebase. Use when Codex needs to answer questions like "how does this feature work?", "what opens this modal?", "what calls this endpoint?", "where does this data come from?", "how does this backend action reach the frontend?", "what path triggers this code?", or "what has to be true for this behavior to happen?"
---

# Trace Project Flow

Use this skill to build an evidence-backed execution map across a repository. Prefer source evidence over memory, and explain the runtime chain in the order a user or system action actually travels.

## Workflow

1. Resolve the target.
   - Identify whether the user means a feature, UI surface, command, route, file, symbol, config key, event, data shape, or generated artifact.
   - If the target is ambiguous, search nearby names first and state the resolved target.
   - If the target does not exist, report likely renames or spelling differences before continuing.

2. Read the target and nearby boundary files first.
   - For backend code, inspect the entry point, adapter/invoker, service/module, config, and tests.
   - For frontend code, inspect the component/view, event handler, API client, state/store, styles only if visual behavior matters, and tests.
   - For cross-boundary behavior, inspect both sides of the bridge: request payload creation, transport/bridge method, polling/subscription, and response submission.

3. Search broadly, then narrow.
   - Prefer `rg` and `rg --files`.
   - Search exact names, file stems, import paths, string ids, route paths, event names, payload keys, CSS classes, test names, config keys, and user-facing labels.
   - Include tests and examples unless the user explicitly asks for production code only.
   - For dynamic registries, inspect maps, plugin loaders, package exports, route registrations, CLI entry points, and lazy imports.

4. Build the execution chain.
   - Start from the user-facing or external trigger when known.
   - Walk through registries, controllers, adapters, providers, services, workers, queues, bridge calls, state changes, UI polling/subscriptions, and final rendering or side effects.
   - Distinguish direct references from runtime reachability.
   - Note fallback paths, mock paths, CLI alternatives, and no-op/skip paths.

5. Record gates and payloads.
   - Capture conditions that must be true: enabled steps/substeps, flags, config values, file existence, available dependencies, selected project state, permissions, cached state, non-empty inputs, or feature toggles.
   - Capture the key data shape crossing important boundaries: request kinds, route params, event names, status fields, decision maps, artifact paths, and report fields.

6. Verify before answering.
   - Use line-numbered reads (`nl -ba path | sed -n 'x,yp'`) for files cited in the final answer.
   - Avoid claiming dead code unless imports, registries, dynamic loading, config strings, tests, and public exports were checked.
   - If the chain has uncertainty because of reflection, generated code, or external callers, say exactly where certainty stops.

## Answer Shape

Keep the answer compact and source-backed:

```text
Target: resolved feature/symbol/path.

What it does: one short paragraph.

Main path:
trigger
-> registry/controller
-> adapter/provider
-> target behavior
-> visible side effect

Conditions:
- Gate or config condition.
- Bypass or fallback.

Key files:
- clickable file reference: role in the chain.
- clickable file reference: role in the chain.
```

For codebase questions, cite local files with clickable absolute links and line numbers. Group references by role rather than dumping every search hit.
