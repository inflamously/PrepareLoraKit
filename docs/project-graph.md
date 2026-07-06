# PrepareLoraKit Project Graph

This is the small map to read before the generated symbol map. It shows the
few connections that explain how the app hangs together.

Open the standalone HTML view at [`docs/project-graph.html`](project-graph.html)
when you want the same information as a browser page.

```mermaid
flowchart TD
  user[User + source dataset]
  source[Original image folder]

  subgraph Entry["Entrypoints"]
    cli[CLI: plk / main.py]
    run_cmd[plk run]
    step_cmd[plk step]
    ui_cmd[plk ui]
  end

  subgraph UI["Desktop UI path"]
    static_app[prepare_lora_kit_ui/static]
    api_js[core/api.js]
    bridge[UiBridge]
    jobs[JobManager]
    interaction[UiInteractionProvider]
  end

  subgraph Config["Config and registries"]
    project_yaml[configs/projects/*.yaml]
    project_registry[project_registry]
    project_config[ProjectConfig]
    step_type_map[STEP_TYPE_MAP]
    substeps[SUBSTEP_REGISTRY]
    network_registry[network_registry]
    network_profile[NetworkProfile]
  end

  subgraph Run["Run orchestration"]
    pipeline[pipeline.run_all]
    ui_execute[JobManager._execute]
    invoke_map[STEP_INVOKE_MAP]
    invoke_adapters[prepare_lora_kit/invoke]
    steps[steps/s0_import ... s9_export]
  end

  subgraph Output["Run state and artifacts"]
    working[outputs/name/dataset]
    reports[outputs/name/reports]
    state_file[outputs/name/.plk_state.json]
    train_config[outputs/name/run_config.yaml]
    export_dir[optional export folder]
  end

  user --> cli
  user --> ui_cmd
  user --> source
  cli --> run_cmd
  cli --> step_cmd
  cli --> ui_cmd
  ui_cmd --> static_app
  static_app --> api_js
  api_js --> bridge
  bridge --> jobs
  jobs --> ui_execute
  jobs --> interaction

  run_cmd --> project_registry
  step_cmd --> project_registry
  bridge --> project_registry
  project_yaml --> project_registry
  project_registry --> project_config
  project_config --> step_type_map
  project_config --> substeps
  project_config --> network_registry
  network_registry --> network_profile

  run_cmd --> pipeline
  pipeline --> invoke_map
  ui_execute --> invoke_map
  step_cmd --> invoke_map
  invoke_map --> invoke_adapters
  invoke_adapters --> steps
  source --> working
  steps --> working
  steps --> reports
  pipeline --> state_file
  ui_execute --> state_file
  steps --> train_config
  steps --> export_dir
  reports --> jobs
```

## The Main Idea

PrepareLoraKit has one pipeline engine with two ways to start it:

- The CLI loads a project config and calls `prepare_lora_kit.pipeline.run_all`.
- The desktop UI starts through `plk ui`, serves the static frontend, and calls
  `prepare_lora_kit_ui.bridge.UiBridge`.
- `UiBridge` hands runs to `prepare_lora_kit_ui.runner.manager.JobManager`.
- Both the CLI path and UI path eventually dispatch step types through
  `prepare_lora_kit.invoke.STEP_INVOKE_MAP`.
- The actual work lives in numbered step packages under `prepare_lora_kit/steps/`.

The important join is the step type string. A project YAML says
`type: CaptionStep`; `STEP_TYPE_MAP` says which config dataclass parses it; and
`STEP_INVOKE_MAP` says which adapter runs it.

## Pipeline Stage Order

The authoritative step order comes from
`prepare_lora_kit_pipeline/configuration.py`. Some directory and substep names
still carry historical numbers, so follow `STEP_ORDER` when the labels disagree.

```mermaid
flowchart LR
  source[Source images]
  s0[ImportStep<br/>s0_import]
  s1[QualityGateStep<br/>s1_source]
  s2[CurateStep<br/>s2_curate]
  s3[UpscaleStep<br/>optional]
  s5[CaptionStep<br/>s5_caption]
  s4[VaeGateStep<br/>s4_vae_gate]
  s6[AuditStep<br/>s6_audit]
  s7[ConfigGenStep<br/>s7_config]
  s8[BucketDryRunStep<br/>s8_bucket]
  s9[ExportStep<br/>optional]
  train[Training handoff]

  source --> s0 --> s1 --> s2 --> s3 --> s5 --> s4 --> s6 --> s7 --> s8 --> s9 --> train
```

## Control And Data Flow

| Layer | What to read | Why it matters |
| --- | --- | --- |
| Entrypoints | `main.py`, `prepare_lora_kit/cli/` | Registers `plk` commands and starts CLI or UI runs. |
| Frontend | `prepare_lora_kit_ui/static/app.js`, `prepare_lora_kit_ui/static/core/api.js` | Boots the static UI and calls the pywebview bridge. |
| UI bridge | `prepare_lora_kit_ui/bridge.py` | Exposes Python methods to `window.pywebview.api`. |
| UI runner | `prepare_lora_kit_ui/runner/manager.py` | Adds job status, step selection, UI interactions, cancellation, and logs. |
| Config | `prepare_lora_kit/project/base.py`, `prepare_lora_kit_pipeline/configuration.py` | Loads project YAML, validates step order, and maps step types to config classes. |
| Dispatch | `prepare_lora_kit/pipeline.py`, `prepare_lora_kit/invoke/__init__.py` | Walks the configured pipeline and calls the right step adapter. |
| Work | `prepare_lora_kit/steps/s0_import` through `prepare_lora_kit/steps/s9_export` | Implements the image preparation stages. |
| State/output | `prepare_lora_kit/utils/state.py`, `outputs/<name>/` | Tracks completed steps and stores the working dataset, reports, and training config. |

## Read This First

1. Start with `README.md` for the user workflow and output layout.
2. Read `prepare_lora_kit/pipeline.py` to see the core CLI run loop.
3. Read `prepare_lora_kit/invoke/__init__.py` to see which step type calls which adapter.
4. Read `prepare_lora_kit/project/base.py` to see how project YAML becomes `ProjectConfig`.
5. For UI behavior, read `prepare_lora_kit_ui/bridge.py`, then
   `prepare_lora_kit_ui/runner/manager.py`.

## What This Map Leaves Out

This is not a full dependency graph. It intentionally leaves out most helper
modules, test files, generated docs, and third-party integration code. Use a
symbol-level code map only after you know which area you are looking at.
