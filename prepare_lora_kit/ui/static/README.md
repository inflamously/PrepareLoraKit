# Static UI File Map

This directory contains the pywebview browser UI for PrepareLoraKit.

| File | Description |
| --- | --- |
| `DESIGN_BASELINE.md` | Documents the project-detail screenshot and app-kit stylesheet as the baseline for future UI pages. |
| `README.md` | Lists each static UI file and its one-line purpose. |
| `app.js` | Waits for pywebview readiness and starts the UI bootstrap. |
| `index.html` | Defines the project-detail desktop shell, controls, workspace columns, statusbar, and modal layer. |
| `styles.css` | Imports all UI stylesheets and defines the shared `.hidden` utility. |
| `+state/index.js` | Combines the state fragments into the shared in-memory UI state object. |
| `+state/jobs.js` | Defines initial in-memory job state for active jobs, run start state, and handled pending requests. |
| `+state/mock_runtime.js` | Defines initial in-memory mock runtime state for mock project and curation coverage settings. |
| `+state/outputs.js` | Defines initial in-memory output directory state and customization tracking. |
| `+state/projects.js` | Defines initial in-memory project list and active project state. |
| `+state/steps.js` | Defines initial in-memory selected pipeline step state. |
| `caption/config.js` | Reads caption step defaults into the form and returns the selected caption model settings. |
| `components/modal.css` | Styles the shared modal overlay, modal container, headers, and footers. |
| `components/modal.js` | Shows and closes content inside the shared modal layer. |
| `components/review_card.js` | Provides reusable review-card behavior for decision buttons, selection, and right-click decision cycling. |
| `core/api.js` | Documents pywebview bridge payloads with JSDoc and returns the Python bridge API. |
| `core/app.js` | Bootstraps app info, projects, saved launch state, event bindings, and the initial render. |
| `core/dom.js` | Contains small DOM helpers for element lookup, text updates, step labels, status flags, and HTML escaping. |
| `core/app-kit.css` | Provides the reusable `nf-*` desktop app component layer adapted from `design/project-detail-view.css`. |
| `core/foundation.css` | Defines active design tokens, base layout defaults, form controls, buttons, panels, and responsive behavior. |
| `core/state.js` | Re-exports the shared state object for existing core state import paths. |
| `job/controller.js` | Builds run requests, starts/cancels jobs, polls job status, opens outputs, and routes pending interactions to modals. |
| `job/job.css` | Adds PrepareLoraKit-specific current-step and selectable run-log behavior on top of the app kit console. |
| `job/view.js` | Renders job status, current step, log text, and action button states. |
| `project/controller.js` | Loads project lists and project details, applies bootstrap state, manages active pipeline selection, and refreshes project state. |
| `project/project.css` | Adds project-specific spacing and substep layout around reusable app-kit pipeline rows. |
| `project/selection.js` | Returns active step types and configured substeps in project pipeline order. |
| `project/view.js` | Renders the project summary, active step toggles, and substep status rows. |
| `shell/events.js` | Wires top-level UI controls to project loading, folder selection, caption input syncing, and job actions. |
| `shell/render.js` | Runs the shared render pass for project steps and job state. |
| `shell/shell.css` | Styles the project-detail shell frame, local status mappings, force row, and small-screen compatibility. |
| `steps/bbox_annotation/bbox_annotation.css` | Styles the bounding-box annotation modal, canvas area, box panel, status, and box rows. |
| `steps/bbox_annotation/bbox_annotation.js` | Orchestrates the region annotation modal, captioning selected boxes, skipping images, and submitting annotations. |
| `steps/bbox_annotation/box_panel.js` | Renders and updates the side panel for selecting, labeling, and deleting annotation boxes. |
| `steps/bbox_annotation/canvas.js` | Handles annotation canvas drawing, pointer events, normalized box coordinates, resizing, and cleanup. |
| `steps/curate_details/curate_details.css` | Styles the curate-details modal, coverage image area, summary metrics, and report path display. |
| `steps/curate_details/curate_details.js` | Shows curation coverage and summary metrics before submitting confirmation to continue. |
| `steps/source_review/card.js` | Builds source-review cards with image thumbnails, quality metadata, and keep/reject/flag controls. |
| `steps/source_review/decisions.js` | Defines source-review decision options and normalizes decision values. |
| `steps/source_review/detail.js` | Renders the selected source-review image, quality summary, score rows, gate findings, and current decision. |
| `steps/source_review/format.js` | Formats source-review quality values and arbitrary score values for display. |
| `steps/source_review/source_review.css` | Styles the source-review modal grid, cards, decision controls, detail panel, and quality sections. |
| `steps/source_review/source_review.js` | Orchestrates source-review state, card selection, detail rendering, and decision submission. |
| `steps/vae_review/components/card.js` | Builds VAE review cards with original, VAE, diff, and hard-mask thumbnails. |
| `steps/vae_review/components/detail.js` | Renders the selected VAE review item, preview tabs, decision buttons, and metrics. |
| `steps/vae_review/components/modal.js` | Creates the VAE review modal structure. |
| `steps/vae_review/utils/decisions.js` | Defines VAE review decisions and normalizes decision values. |
| `steps/vae_review/utils/format.js` | Formats VAE image dimensions and numeric metrics for display. |
| `steps/vae_review/utils/views.js` | Defines available VAE preview views and normalizes the active view. |
| `steps/vae_review/vae_review.css` | Styles the VAE review modal, thumbnail grid, detail preview, tabs, actions, and metrics. |
| `steps/vae_review/vae_review.js` | Orchestrates VAE review state, card selection, view changes, decision updates, and submission. |
