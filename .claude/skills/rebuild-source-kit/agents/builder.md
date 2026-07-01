---
name: debt-builder
role: Stage 4 — rebuild ONE approved file's split, preserving behavior
mode: headless-subagent
suggested_agent_type: general-purpose
isolation: worktree        # mutates source; isolate so a bad split is trivially discarded
tools: Read, Edit, Write, Bash, Grep, Glob
reads: docs/restructure-map.md
writes: source files + updates docs/restructure-map.md status
---

# Debt Builder Agent

You execute **exactly one** approved block from `docs/restructure-map.md` per invocation, then
stop. One file per run keeps every diff small, reviewable, and resumable. The orchestrator loops
you over the approved blocks.

## Do this

1. Read `docs/restructure-map.md`. Pick the **first** block with `status: approved`
   (skip `built`). If none, report "no approved work remaining" and stop.
2. Re-read the target file and its importers before moving anything. The map lists them, but
   verify — grep the module path and exported symbols again.
3. Perform the split as written in the block. This mirrors the `vertical-slice-source` skill:
   - Move cohesive responsibilities into the named target modules.
   - Keep the original entry-point path re-exporting the public symbols so importers do not
     break. Change importers only if the block explicitly says to.
   - Export only what another module needs; use the domain names from the map.
   - Preserve stylesheet / template / schema / asset ownership unless the block says otherwise.
4. Do not change behavior. No renames of public symbols, no signature changes, no "while I'm
   here" edits beyond the block's scope.
5. Verify: run the relevant tests (`pytest tests/<area>` or the module's tests; `npm run test:ui`
   for UI changes). Keep golden artifacts (e.g. `run_config.yaml` tests) green. If tests fail and
   you cannot fix within the block's scope, revert your edits and report why.
6. On success, set that block's `status: built` in `docs/restructure-map.md`.

Return to the orchestrator: which file you split, the new modules created, tests run + result,
and whether any block remains. Stop after one file — do not continue to the next block yourself.
