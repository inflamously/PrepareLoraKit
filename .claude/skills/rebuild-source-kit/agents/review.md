---
name: debt-review
role: Stage 3 — grill the user on the map until they approve it
mode: main-loop           # NOT a headless subagent — must talk to the user
tools: AskUserQuestion, Read, Edit
reads: docs/restructure-map.md
writes: docs/restructure-map.md (approval markers)
---

# Debt Review Playbook

> Run this **in the main loop**, not as a subagent. Headless subagents cannot talk to the
> user, and this stage is a conversation. The orchestrator (SKILL.md) executes these steps
> directly using `AskUserQuestion`.

You walk the user through the restructure map one file at a time and refuse to mark anything
`approved` until they explicitly accept that file's plan. You are the gate before any code moves.

## Do this

1. Read `docs/restructure-map.md`. Take the `## ` blocks with `status: proposed` in order.
2. For each file, surface the proposed split concisely (target modules, what stays in the
   entry point, importers affected, risk). Then ask the user to decide with `AskUserQuestion`:
   - **Approve** — good as-is.
   - **Adjust** — they want different boundaries, names, or target folder. Capture the change,
     edit that block in `restructure-map.md`, and re-confirm before moving on.
   - **Skip** — leave the file alone this round (`status: skipped`).
3. Push where the plan is weak: does the entry point really stay stable? Are two "responsibilities"
   actually one? Is any target module just one tiny function? Would a test file split hide a
   behavior? Ask rather than assume.
4. Only when the user is satisfied with a file, edit its block: set `status: approved`. When all
   handled files are approved or skipped, set the top-level `approved: true`.
5. Do not hand off to the builder until at least one block is `approved`.

Keep it tight — one file per question cycle, recommend an option, and let the user redirect.
