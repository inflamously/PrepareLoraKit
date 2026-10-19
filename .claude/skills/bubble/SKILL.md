---
name: bubble
description: bubble-tracks — iterative, fog-of-war planning on a linear track of task bubbles (S ○──○──❓──○ F) stored in .bubble-tracks/ (one .json per track, switchable). Use when the user runs /bubble or $bubble (e.g. /bubble switch <track> to resume), asks to plan/sketch a task, asks "what's next" or "where are we", marks something done, or when an edit is blocked because the active bubble is fog/unplanned.
---

# bubble-tracks (pointer)

The real skill lives at `.agents/skills/bubble/` — this file only registers it with Claude Code.

1. Read `.agents/skills/bubble/SKILL.md` in full and follow it.
2. Run the CLI as `node ".agents/skills/bubble/scripts/cli/bubble.js" <command> [args]`
   (wherever that SKILL.md says "<dir containing this SKILL.md>", use `.agents/skills/bubble`).
3. If invoked with arguments (e.g. `/bubble switch my-track`), run exactly that command through the CLI and show the result.
