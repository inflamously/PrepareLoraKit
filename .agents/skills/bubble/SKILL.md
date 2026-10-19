---
name: bubble
description: bubble-tracks — iterative, fog-of-war planning on a linear track of task bubbles (S ○──○──❓──○ F) stored in .bubble-tracks/ (one .json per track, switchable). Use when the user runs /bubble or $bubble (e.g. /bubble switch <track> to resume), asks to plan/sketch a task, asks "what's next" or "where are we", marks something done, or when an edit is blocked because the active bubble is fog/unplanned.
---

# bubble-tracks

A plan is a linear track from **S**tart to **F**inish. Each bubble is a task:
`●` done · `◐` active · `○` todo · `❓` fog (unplanned — the human plans it).
Plan only as far as you can see. The rest stays fog until it's reached.

The track line reads `S ●──●──◐──○ F   prev ‹ ◐ active › next`, with each label cut to 20 characters.
So **titles are short names (2–4 words)**, like `Remove nesting` or `Fog-only fill`. Put details, scope and file lists in a `hint`.

## The CLI

Every change goes through the CLI. **Don't hand-edit anything in `.bubble-tracks/`.** The CLI lives next to this file:

```
node "<dir containing this SKILL.md>/scripts/cli/bubble.js" <command> [args]
```

Run it from the repo root, or pass `--dir <repo>`. The CLI speaks the **bubble language**, the same words the human uses:

| Command | Effect |
|---|---|
| `show` | Render the track and list its bubbles with addresses. Exits **3** if the active bubble is fog. |
| `switch [name] [title]` | Resume track `<name>`, or create it if it doesn't exist. It becomes current. No name: resume the current track (else the default `track`). |
| `create <name> [title]` | Create a new track (refuses if it exists) and make it current |
| `tracks` | List all tracks, current marked `→` |
| `close <name> --force` | Finish a track for good, after the human confirms: read-only, no reopen. Also closes all its forks (side tracks stay open) and pops its parent bubble. Without `--force` it refuses and lists every track it would close. |
| `delete <name> --force` | Delete a track that isn't current, after the human confirms |
| `init <title>` | Create the default track (`.bubble-tracks/track.json`) |
| `fork [N] <name>` | **Build on** bubble N in a new child track `<name>`, titled after the bubble, and make it current. The bubble keeps its state and gets `fork` (relative path to the child); the child gets `parent` (relative path, the bubble's stable `id`, and its title for display). The bubble waits for its fork. |
| `diverge [N] <name> [title]` | Go **a different direction** from bubble N in a new side track `<name>` (titled after the bubble unless you give a title), and make it current. The bubble (any state) adds the path to its `sides`; the side track gets `origin`. Nothing waits for it. |
| `add <title>` · `add ?` | Append a todo (or fog) bubble |
| `insert at N <title>` · `insert at N ?` | Insert a todo (or fog) bubble at position N |
| `remove N` · `remove N:M` | Delete a bubble or a range |
| `move N to M` · `move N:M to M` | Move a bubble or block so it starts at position M |
| `move N --to <track>` · `move N:M --to <track>` | Move a bubble or block to the end of another existing track (state, type and hint kept; new ids). Refuses bubbles with a fork or side track. |
| `rename N <title>` | Retitle a planned bubble (not fog) |
| `title <text>` | Rename the track itself (keep it short too) |
| `handoff <note>` · `handoff -` | Save (or clear) the note a fresh chat reads to resume this track |
| `hint N <text>` · `hint N -` | Attach (or clear) the human's note for that bubble |
| `fog [N \| N:M] [TYPE]` | Turn bubbles into fog. Done bubbles need `--force`, after the human confirms. |
| `type [N] <TYPE>` | Record the human's fog classification |
| `fill [N] <title>` | The human's content for a fog bubble: fog → todo |
| `done` | Pop the active bubble, then ⏸ stop |

Every bubble command acts on the **current track**. Each track is its own idea or implementation, with its own fog gate.

`--to <track>` on `add`, `insert` and `hint` writes into another existing track instead, and the current track stays current. Use it to record future work for another track while you walk this one, rather than `switch`, `add`, `switch` back.

N: position on the track; omitted = the active bubble. `N:M` = N through M, inclusive.
TYPE: `known-known` · `known-unknown` · `unknown-known` · `unknown-unknown` (or `kk` · `ku` · `uk` · `uu`).

### The human's commands

When the human writes a line in the bubble language, like `bubble move 2 to 3`, `/bubble remove 5` or `bubble fog 4:8`, run it **exactly**: pass the words after `bubble` to the CLI unchanged, then show the result. Don't reinterpret, batch or "improve" it. If the CLI rejects it, show the error and the usage line, and don't guess a fix. Plain-language requests ("drop the last one") are fine too; translate them into these commands and show what you ran.

## How to work

0. **Resume or start.** `/bubble switch <name>`, often the first line of a fresh chat, runs `switch <name>`:
   - `resumed track "<name>"`: you have no memory of this track, so the track is your context. Read every bubble, its `↳` hint and the `✎ handoff` note, then say in one line where you are (prev ‹ active › next) and continue at the active bubble with the usual rules. It's a ⏸ stop if the human hasn't said go.
   - `created track "<name>"`: it's new, so go to step 1.

   **Apply `switch` right away. Don't ask why, and don't ask what the track is for first.** If you see a better name, use it and say so in one line instead of asking. For example, `switch single commit` becomes `switch single-commit "Single commit"`, and if `single-commit` looks like a typo of an existing track, say which one. If the human hasn't said what the track is for, the sketch step asks.
1. **Sketch.** With no track, `switch <name>` (or `init`), then make one rough pass from S to F. Steps that are clear become todo bubbles with short titles; add a `hint` when a step needs more words. Anything unclear becomes `add --fog` with no detail. Keep it short and don't over-plan.
   - **Then always classify every fog bubble in one go.** Do this after every sketch, without skipping it. List every fog bubble by number and ask the human to answer each line with either:
     - `N: <what they think it is>`: their content. Run `fill N` with a short title, and put the detail in a `hint`.
     - `N:kk` · `N:ku` · `N:uk` · `N:uu`: the knowledge level. Run `type N`.

     For example: `1:uk  2: tighten the fog gate  3:uu`. The levels shape everything after this, because they decide how you work each bubble in step 3.
2. **Walk.** Run `show`. If the active bubble is known, implement it, then run `done`. Read the bubble's `↳` hint first: it's the human's steer for that bubble.
3. **Hit fog → STOP.** When the active bubble is fog (`show` exits 3, or an edit is blocked):
   - **Never plan fog yourself.** Don't invent its content and don't run `fill` on your own.
   - Ask the human to classify it, using the same `N: text` / `N:kk|ku|uk|uu` reply format (and if more fog lies ahead, ask about all of it at once):
     - **known-known**: they write the bubble.
     - **known-unknown**: you research or spike options, they pick.
     - **unknown-known**: you surface what the codebase and docs already say, they confirm.
     - **unknown-unknown**: you interview them, one question at a time.
   - Record the answer with `type`. The type can change as you go.
   - Only after the human gives or approves the content, run `fill` (single task). If it's really several tasks, `fill` it with the first and `insert at` the rest right after it on the same line.
4. **⏸ Stop after every bubble.** After `done`, the CLI prints a ⏸ line. Show the track, summarize what you did, and **wait for the human** before starting the next bubble. This is their chance to move, insert, remove, rename, hint or fog bubbles. Start the next bubble only when they say go (or give an edit, then go).
5. **Hand off when the chat gets heavy.** At a ⏸ stop, offer a fresh chat if:
   - this chat was compacted or summarized,
   - about 3 or more bubbles were finished in this chat, or
   - the human says the context is too long.

   First save what only this chat knows: `handoff <note>` (what's half done, the decisions made and why, gotchas, and the next concrete step), plus `hint`s on the bubbles ahead. Keep the note to a few lines. Then tell the human: *"Context is getting heavy. Run `/clear`, then `/bubble switch <name>`."* The CLI prints that exact line, track name included. Don't push it: if they want to keep going, keep going.
6. **Show progress.** After every change, show the user the rendered line the CLI prints. Most agents have no status line, so this is how they see the track.
   When the human asks for a list or overview (`list`, "list tracks", "where are we"), run `tracks` (or `show` for one track) and paste its output **unchanged in a code block**: every line, aligned as printed, nothing summarized or reworded. Then add at most a few short bullets on what stands out (current track, broken or finished tracks).

## Fork or diverge: keep each track to one domain

A track stays clean when every bubble on it serves one goal. If the human asks for something that doesn't belong to the active bubble, such as a new feature, another domain or a side idea, don't `add` it to this track, because that poisons its workflow. Split it off:

- **`fork`**: the request **builds on** the active bubble (it goes deeper into the same idea). The bubble waits until its fork is finished.
- **`diverge`**: the request goes **a different direction**. The side track remembers where it came from, but nothing waits for it.

**Ask before splitting.** Suggest the one you think fits, with a one-line reason, and let the human pick: `fork`, `diverge`, or keep it on this track. For example: *"This goes a different direction from 'Login'. Diverge into `auth-sso`? (fork / diverge / keep here)"*. Run the command only after they answer. Then the new track is current and starts **fresh**: ask the human what to do around the new goal, sketch it (step 1), and classify all fog. Small, related follow-ups (a missing step of the same goal) still go on the current track with `insert`.

Work that belongs to a track that **already exists** doesn't need a split: record it there with `add <title> --to <track>` (plus `hint N <text> --to <track>`) and keep walking. To regroup bubbles that ended up on the wrong track, `move N:M --to <track>`.

Links use the bubble's stable `id` (from the track's `nextId` counter), so `move`, `insert` and `remove` never break them.

A fork stays in sync with its bubble. `title` on the fork renames the bubble, and `rename` on the bubble retitles the fork. The bubble can't be popped until its fork is finished (it has at least one bubble and all are done). When the fork's last bubble is popped, the parent bubble pops too, and so on up the chain. A side track from `diverge` never syncs.

A **closed** track (`close`) is read-only: every bubble command on it refuses, and its line shows 🔒 closed. To keep working, `fork`, `diverge` or `switch`. A closed fork counts as finished, so closing it pops its parent bubble; closing a track closes all its forks too. A closed parent is skipped: its child runs on, but pops and title syncs never reach it.

## Fog gate

Before editing project files, check `show`. If it exits 3, don't edit; go to step 3. Some agents (Claude Code, Codex CLI, Gemini CLI) also enforce this with a hook that blocks edits while the active bubble is fog. Edits under `.bubble-tracks/` are always allowed.
