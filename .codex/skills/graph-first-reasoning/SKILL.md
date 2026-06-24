---
name: graph-first-reasoning
description: Convert a messy, unclear, diagnostic, dependency-tracing, planning, debugging, or "what should I do?" problem into a small reasoning graph before answering. Use when graphing concrete entities, relationships, blockers, or next actions would make the answer clearer; avoid when a direct answer would be simpler and no graph adds value.
---

Use graph only when it helps debugging, planning, dependencies, or unclear problems.
For simple facts/math/translation/syntax, answer directly.

When graphing, output:
NODES:
EDGES:
KEY PATH:
ACTION:
ANSWER:

Keep nodes concrete. Use only useful edges. Prefer the smallest next action.

User prompt:
{{input}}