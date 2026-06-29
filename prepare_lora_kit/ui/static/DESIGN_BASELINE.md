# Static UI Design Baseline

The project-detail view is the baseline design for the desktop UI.

Reference files:

- `../../../design/project-detail-view.png` is the visual target.
- `../../../design/project-detail-view.css` is the source design kit.
- `styles/*.css` is the shipped, repo-integrated design kit used by the app, split one file per component.

## System

- Use `styles/tokens.css` for the active design-token contract (the `:root` custom properties); override these to reskin the kit.
- Use `core/foundation.css` for reset rules and base element defaults (it depends on the tokens above).
- Use the per-component files in `styles/` for reusable `nf-*` desktop app primitives: window shell, appbar, workspace columns, panels, form fields, buttons, pills, pipeline rows, console output, statusbar, toolbars, cards, metrics, and key/value lists. Each component owns one file (e.g. `styles/button.css`, `styles/panel.css`), and `styles/index.css` is the self-contained barrel (tokens + every component) for importing the whole kit at once.
- Keep page-specific layout in the feature stylesheet that owns the page, for example `shell/shell.css`, `project/project.css`, or `job/job.css`.
- Do not import files from `design/` at runtime; packaged static assets must live under `prepare_lora_kit/ui/static/`.

## Project Detail Pattern

- The first viewport is an application workspace, not a landing page.
- Use `.nf-window` as the full pywebview content frame with `.nf-appbar`, `.nf-workspace`, and `.nf-statusbar`.
- Do not render custom window chrome inside pywebview; the native app window is the only window frame.
- Use three workspace columns for project detail pages: config rail, primary workflow panel, and run/output panel.
- Use `.nf-panel` for framed tools and repeated cards only. Avoid nesting cards inside cards.
- Use `.nf-console` for run output and preserve selectable text.

## Future Pages

- Prefer existing `nf-*` classes before adding page-local styling.
- Add new shared primitives to the matching `styles/<component>.css` (or a new per-component file) only when more than one page will use them.
- Keep UI bridge IDs, payload shapes, and frontend API call sites stable unless the bridge documentation in `core/api.js` is updated at the same time.
- Review modal pages currently inherit the shared tokens; their layouts have not been fully redesigned to this baseline yet.
