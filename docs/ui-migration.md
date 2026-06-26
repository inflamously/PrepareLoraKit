# UI Migration — Off the manual DOM/render layer

Status: proposal · Author: discussion 2026-06-26 · Scope: `prepare_lora_kit/ui/static/`

## TL;DR

The UI is **44 files / ~2,700 LOC** of plain ES modules, served as static files
into a **pywebview** desktop window (`cli/ui.py`) with **no build step**. The
stated pain is the **manual DOM/render layer** (`$()`, `setText()`, hand-wired
`addEventListener`, imperative `render()`).

Recommendation — do these in order, each independently shippable:

1. **Add TypeScript type-checking (`checkJs`, no rewrite, no build).** Cheap
   foundation. Catches a whole class of bugs *before* the rewrite touches them.
2. **Adopt Preact + htm + signals (no build step).** Replaces the imperative
   render layer with reactive components while keeping the zero-build,
   static-served deployment that pywebview relies on.
3. **(Optional, later) Graduate to a compiled framework (Svelte/Solid) with a
   Vite build** — only if the no-build ergonomics stop paying off.

Do **not** start with a from-scratch React/Vite rewrite. It is 10× the work,
throws away the working `+state`/controller split, and changes the deployment
model for no proportional gain.

---

## Why this came up

Two real bugs in one button (`openInput`), both found 2026-06-26:

1. `job/controller.js` read `state.project.input_dir` — there is no
   `state.project`; the field is `state.inputDir`. Silent `undefined`.
2. `shell/events.js` did `addEventListener("click", openInput)` **without
   importing `openInput`** → `ReferenceError` in `bindEvents()`, so the listener
   was never attached.

Neither is a "framework" bug. **A framework would not have caught either.** A
type checker catches **both** instantly (`Property 'project' does not exist`,
`Cannot find name 'openInput'`). That is the core argument for ordering: types
first, framework second. They solve different problems.

---

## Current architecture (what we keep vs. replace)

```
+state/        per-domain state slices merged into one mutable `state` object   → KEEP (becomes signals/stores)
core/api.js    pywebview bridge wrapper, already JSDoc-typed (22 bridge methods) → KEEP
core/dom.js    $(), setText(), setShellStatus(), escapeText()                    → REPLACE (framework owns the DOM)
shell/render.js  manual render() fan-out calling each view                       → REPLACE (reactivity replaces it)
shell/events.js  hand-wired addEventListener for every control                   → REPLACE (events bind in markup)
*/view.js      imperative DOM mutation (the pain)                                → REWRITE as components
steps/*        annotation/review screens                                         → REWRITE incrementally
```

The keep/replace split is the whole reason a framework migration is feasible
here: the **data layer (`+state`, `core/api.js`) is already separated** from the
**render layer**. We only rewrite the render layer.

### The pain, concretely — `job/view.js`

```js
// CURRENT: imperative, every property set by hand, easy to desync
cancelButton.disabled = TERMINAL_STATUSES.has(job.status) || cancelling;
cancelButton.textContent = cancelling ? "Cancelling..." : "Cancel";
openOutput.disabled = !job.result?.output_dir;
currentStepLabel.classList.add("hidden");   // and remove() elsewhere — manual toggle
```

```js
// AFTER (Preact + htm + signals): declarative, no desync possible
html`
  <button onClick=${cancelRun} disabled=${isTerminal(job) || cancelling}>
    ${cancelling ? "Cancelling..." : "Cancel"}
  </button>
  <button onClick=${openOutput} disabled=${!job.value?.result?.output_dir}>Open output</button>
  ${job.current_step && html`<span class="current-step">…</span>`}
`;
```

The component re-runs when the `job` signal changes — no `render()` fan-out, no
`classList` toggling, no "did I forget to reset this on the idle branch?" The
manual text-selection guard in `renderJob()` (`hasSelectionInside`) also
disappears, because the log node stops being reassigned on every poll.

---

## Step 0 — Make failures loud (DONE 2026-06-26)

Before any of this, debugging was blind. Three compounding causes meant *any*
uncaught error silently half-booted the app with no trace:

1. The entry point `init()` is an **async function used directly as an event
   listener** (`app.js`). Its promise was never awaited or `.catch`-ed, so a
   throw became a swallowed unhandled rejection — and because `init()` runs the
   whole boot sequence top-to-bottom, one early throw skipped `bindLibraryEvents`,
   `loadLibrary`, and `render` with no indication.
2. **No global error handlers** existed anywhere (`window.onerror`,
   `error`, `unhandledrejection`).
3. **pywebview shows no console** unless launched with `--debug` (`cli/ui.py`),
   so even `console.error` was invisible.

Fix shipped:

- `core/errors.js` — `installErrorSurface()` installs catch-all `error` /
  `unhandledrejection` handlers that log **and** paint a dismissible on-screen
  banner; `runBoot(fn)` wraps the async entry point so its rejection is surfaced.
- `app.js` now calls `installErrorSurface()` first, then
  `runBoot(init)` on `pywebviewready`.

Result: the exact `openInput` `ReferenceError` that started this — and anything
like it — now shows a red banner instead of a silent no-op. Use `--debug` for the
full DevTools console during development.

## Step 1 — TypeScript `checkJs` (foundation, ~half a day)

No `.ts` files, no bundler, no runtime change. TypeScript runs as a *checker*
over the existing `.js`.

1. `npm i -D typescript`
2. `tsconfig.json`:
   ```jsonc
   {
     "compilerOptions": {
       "checkJs": true,
       "noEmit": true,
       "allowJs": true,
       "module": "esnext",
       "target": "es2022",
       "moduleResolution": "bundler",
       "strict": true,
       "lib": ["es2022", "dom", "dom.iterable"]
     },
     "include": ["prepare_lora_kit/ui/static/**/*.js"]
   }
   ```
3. Type the merged `state` object once (extend the JSDoc already in
   `+state/index.js`). From then on `state.project.input_dir` is a red squiggle.
4. `package.json`: `"typecheck": "tsc --noEmit"`; run it alongside `test:ui`.

You already started this — `core/api.js` has JSDoc `@typedef`s. This just turns
them on and makes them enforced. **Ship this regardless of whether step 2 ever
happens** — it pays for itself the next time someone fat-fingers a state field.

## Step 2 — Preact + htm + signals (the actual fix, ~1–2 weeks incremental)

**Why Preact + htm specifically, for *this* app:**

- **No build step.** `htm` uses tagged template literals instead of JSX, so
  there is nothing to compile. Vendor `preact`, `@preact/signals`, and `htm` as
  ESM and import them directly — exactly the static-served model pywebview
  already uses (`cli/ui.py` serves the folder over `http.server`). Svelte/Solid/
  Vue-SFC all *require* a compiler, which means adding Vite + a build artifact to
  the Python packaging. Preact+htm keeps deployment identical.
- **~4KB.** Desktop webview, but still: no reason to ship a heavy runtime.
- **Signals map 1:1 onto the existing `+state` slices.** Each slice field becomes
  a signal; controllers keep mutating state, views re-render automatically. The
  `render()` fan-out in `shell/render.js` is deleted.
- **JSDoc/TS types carry over** from step 1 — Preact is fully typed.

**Migration tactic — strangle, don't rewrite:**

1. Mount one Preact root for the **least-coupled screen first** (good candidate:
   `steps/vae_review/` or the job status panel — self-contained, clear state).
2. Convert its `+state` slice fields to signals; leave the rest as the plain
   mutable object (signals and plain state coexist fine during transition).
3. Delete that screen's `view.js` + its `events.js` bindings; events now live in
   the component markup.
4. Repeat screen by screen. `core/api.js` and the controllers are untouched.
5. When the last view is converted, delete `shell/render.js`, `shell/events.js`,
   and the DOM helpers in `core/dom.js` (keep `escapeText` only if still used).

**Risk / cost:**

- pywebview's webview is modern Chromium/WebKit, so ESM + template literals run
  natively — no polyfills.
- Main risk is the two annotation/canvas screens (`steps/bbox_annotation/`) which
  do direct canvas work; wrap the canvas in a component but keep imperative
  drawing inside a `ref` — don't fight the framework there.
- Vendoring third-party ESM means pinning versions in-repo (no CDN at runtime —
  the sandbox/desktop app may be offline). Add them under `ui/static/vendor/`.

## Step 3 — Compiled framework (only if needed, later)

If, after step 2, the no-build constraint becomes the thing slowing you down
(e.g. you want SFCs, scoped CSS, or Solid's finer reactivity), graduate to
**Svelte or Solid + Vite**. This means:

- Add a Vite build; output to `ui/static/dist/`.
- Point `cli/ui.py`'s static server / `index.html` at the built bundle.
- Package the build step into the Python release flow.

Defer this until there's a concrete reason. Steps 1–2 likely settle the pain.

---

## Decision summary

| Pain | Tool | Build step? | Effort | Order |
|------|------|-------------|--------|-------|
| Silent failures / blind debugging | global error surface (`core/errors.js`) | none | done | **0 (done)** |
| Wrong shapes / undefined / missing imports (today's bugs) | TS `checkJs` | none | ~½ day | **1st** |
| Imperative DOM, `render()` fan-out, event wiring (stated pain) | Preact + htm + signals | none | ~1–2 wk | **2nd** |
| Want SFCs / scoped CSS / compiled reactivity | Svelte/Solid + Vite | yes | larger | only if needed |

**Rejected:** full React + Vite rewrite up front — highest cost, changes
deployment, discards the working state/controller split, and doesn't address the
type bugs any better than step 1 does.
