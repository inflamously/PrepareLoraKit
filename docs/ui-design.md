# UI Design — Baseline & nf-* Component Kit

The single source of truth for the desktop UI's visual design: the baseline
layout pattern, the `nf-*` component kit, and the rules every component must
follow. (Merged from the former `prepare_lora_kit_ui/static/DESIGN_BASELINE.md`
and `prepare_lora_kit_ui/static/styles/design.md`.)

Paths below are relative to the repository root.

## Reference

- `design/project-detail-view.png` — the visual target for a single project.
- `design/project-browser-view.png` — the visual target for the project library.
- `prepare_lora_kit_ui/static/styles/*.css` — the shipped, repo-integrated `nf-*`
  design kit, split one file per component.

The project-detail view is the baseline design for the desktop UI.

## System

- Use `prepare_lora_kit_ui/static/styles/tokens.css` for the active design-token
  contract (the `:root` custom properties); override these to reskin the kit.
- Use `prepare_lora_kit_ui/static/core/foundation.css` for reset rules and base
  element defaults (it depends on the tokens above).
- Use the per-component files in `styles/` for reusable `nf-*` desktop app
  primitives: window shell, appbar, workspace columns, panels, form fields,
  buttons, pills, pipeline rows, console output, statusbar, toolbars, cards,
  metrics, and key/value lists. Each component owns one file (e.g.
  `styles/button.css`, `styles/panel.css`), and `styles/index.css` is the
  self-contained barrel (tokens + every component) for importing the whole kit
  at once.
- Keep page-specific layout in the feature stylesheet that owns the page, for
  example `shell/shell.css`, `project/project.css`, or `job/job.css`.
- Do not import files from `design/` at runtime; packaged static assets must
  live under `prepare_lora_kit_ui/static/`.

## Project Detail Pattern

- The first viewport is an application workspace, not a landing page.
- Use `.nf-window` as the full pywebview content frame with `.nf-appbar`,
  `.nf-workspace`, and `.nf-statusbar`.
- Do not render custom window chrome inside pywebview; the native app window is
  the only window frame.
- Use three workspace columns for project detail pages: config rail, primary
  workflow panel, and run/output panel.
- Use `.nf-panel` for framed tools and repeated cards only. Avoid nesting cards
  inside cards.
- Use `.nf-console` for run output and preserve selectable text.

## Component Kit Rules

Conventions every component in `styles/` must follow. These travel with the
kit; keep them true if you copy `styles/` into another project.

### Gold glow: every golden / glowing element must animate its glow

Any interactive element that uses the gold accent to "light up" (primary
buttons, checked checkboxes, and anything added later in the same spirit) must
obey all three rules below. The reference implementations are
`.nf-btn--primary` (`styles/button.css`) and `.nf-check` (`styles/forms.css`).

#### 1. Use the glow tokens — never hand-roll a shadow

| State | Token |
| --- | --- |
| Resting "on" glow (e.g. a checked box) | `--glow-gold` |
| Hover / pressed "brighten" | `--glow-gold-strong` |

Both live in `tokens.css`. The brighten-on-hover step is what reads as the
"street lamp at night" effect — go from no glow (or `--glow-gold`) at rest to
`--glow-gold-strong` on hover.

#### 2. Transition the glow — the element must list `box-shadow`

The glow has to fade in/out, not snap. Every glowing element's `transition`
must include `box-shadow` with the shared timing tokens so the feel is uniform:

```css
transition: var(--transition-color), box-shadow var(--dur-fast) var(--ease-out);
```

`--transition-color` already animates color/background/border-color; append the
`box-shadow` segment (and `transform` if the element nudges on press, like
`.nf-btn`). Do not introduce a different duration or easing — `--dur-fast` /
`--ease-out` are the kit-wide values.

#### 3. Win the cascade — guard the hover/active state with doubled specificity

A host's generic element reset (`button:hover:not(:disabled)`, `input:focus`, …)
is specificity `(0,2,1)` and will otherwise repaint the background dark, killing
the glow. Raise the glowing state above it by doubling the real classes already
on the element (`(0,3,0)` beats `(0,2,1)`, order-independently):

```css
.nf-btn.nf-btn--primary:hover { background: var(--gold-400); box-shadow: var(--glow-gold-strong); }
.nf-check:checked:hover       { box-shadow: var(--glow-gold-strong); }
```

Both classes in the doubled selector must genuinely be present in the markup
(`class="nf-btn nf-btn--primary"`, `<input class="nf-check" checked>`) so the
selector stays honest rather than a synthetic specificity hack.

#### Checklist for a new glowing element

- [ ] Glow uses `--glow-gold` / `--glow-gold-strong` (no inline shadow values).
- [ ] `transition` includes `box-shadow var(--dur-fast) var(--ease-out)`.
- [ ] Hover/active glow state has specificity `≥ (0,3,0)` via doubled real classes.
- [ ] Dark text on gold uses `--accent-ink`; it stays readable through hover.

## Future Pages

- Prefer existing `nf-*` classes before adding page-local styling.
- Add new shared primitives to the matching `styles/<component>.css` (or a new
  per-component file) only when more than one page will use them.
- Keep UI bridge IDs, payload shapes, and frontend API call sites stable unless
  the bridge documentation in `core/api.js` is updated at the same time.
- Review modal pages currently inherit the shared tokens; their layouts have not
  been fully redesigned to this baseline yet.
