# Core Pipeline Run Model

PrepareLoraKit runs the app pipeline as an ordered sequence of steps and
substeps.

## Pipeline Structure

- A pipeline is the top-level ordered workflow.
- A pipeline contains one or more steps.
- Each step can contain one or more substeps.
- Substeps always run in their configured order inside the parent step: first,
  second, third, and so on.
- Substeps do not need to show dependency text in the app because their order is
  fixed by the parent step.

## Step States

Steps can be:

- `active`: included in the app run.
- `deactive`: excluded from the app run by clearing its checkbox.
- `optional`: excluded by default, but available when explicitly checked. The
  SeedVR2 upscale step is optional.

## Run Order

For a normal app run, the pipeline starts at the first pending active step and
continues through later active steps in pipeline order.

If force run is selected, the app runs the complete active pipeline from start to
end, including steps that were already completed.

Any active step can be skipped for the current run by deactivating its checkbox.
If a deactivated step is required by a later active step, that prerequisite must
already be completed in the selected output state.
