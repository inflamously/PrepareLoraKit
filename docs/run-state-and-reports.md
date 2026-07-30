# Run state and reports

Two files describe what a step did, and they live side by side under the
project's output folder:

```
<output_dir>/
  .plk_state.json                     ← run state: what the pipeline believes
  reports/<StepType>_report.json      ← the step's own account of what it did
  dataset/                            ← the working copy the steps operate on
```

`.plk_state.json` is what the pipeline reads to decide what to run, and what the
step list in the UI renders; the report is the artifact backing each of its
claims. The rules below keep the two saying the same thing, and the step list
checks one against the other rather than trusting the manifest alone.

## The rules

**Every step writes a report, including when it does nothing.** A step that
returns without leaving a report is indistinguishable on disk from a step that
never ran. A "no work" run writes the same key set as a successful one plus
`skipped: true` and a `reason` (`QualityGateStep` is the exception that proves
the rule: its report is a per-image map, so "nothing scored" is a written `{}`).

**A report never outlives the run state that describes it.** `--force` resets the
run state of the selected step and everything downstream; the same steps' reports
are deleted in the same breath, by `discard_step_reports`. Only
`<StepType>_report.json` files are removed — coverage plots, previews and
`caption_verdicts.json` are artifacts that deliberately outlive one step.

**Report paths come from one place.** `step_report_path(output_dir, step_type)`
in `prepare_lora_kit/report.py` owns the `reports/<StepType>_report.json`
convention. Nothing spells it out by hand; a step's fallback path and the path
its invoker passes are then the same path by construction.

**A record whose report is gone is not trusted.** The step list checks each
recorded run against its file on disk. Delete `reports/` (or one report in it)
and those steps come back as **stale** instead of `done`, and the project card
drops from *completed* to *draft*. This applies only to records that claim a run
— see `records_a_run` — so manifests written before outcomes were tracked, and
the fabricated record for a pre-existing working dataset, are never flagged.

## Status vs outcome

A step that ran but did no work is still persisted as `status: done`, with
`outcome: skipped` and an `outcome_reason` beside it:

```json
"CurateStep": {
  "status": "done",
  "completed_at": "2026-07-30T21:04:11",
  "enabled_substeps": ["duplicate_check"],
  "outcome": "skipped",
  "outcome_reason": "no images",
  "substeps": {"duplicate_check": {"status": "skipped", "reason": "no images"}}
}
```

The split is deliberate. `status` is machine-facing: prerequisite validation and
the resume/skip policy read it, and a step that legitimately had nothing to do
must neither block the steps after it nor re-run on every pass. `outcome` is
user-facing: the UI renders it as a **skipped** badge with the reason as its
tooltip, rather than a green **done** that the reports folder contradicts.

`plk run`/`plk step` say the same thing on the console, through `describe_skip`.

So the badges a step can show, all derived in `payloads._step_status`:

| Badge | What it means |
| --- | --- |
| `pending` | Never ran, or its state was invalidated by `--force`. |
| `running` | The in-flight job is on this step (live snapshot, not persisted). |
| `done` | Ran, did work, and its report is on disk. |
| `skipped` | Ran, reported no work. Satisfied — a plain re-run passes over it. |
| `stale` | Recorded a run whose report is missing. Re-run to rebuild it. |

## Substeps

`enabled_substeps` records the substeps the *last* run actually enabled, and each
one gets its own entry under `substeps`. A substep with no entry has not run —
it is `pending`, not `done`. The one exception is a manifest written before
substeps were tracked at all (no `substeps` key anywhere in the record), where a
substep inherits its parent's status; see `RunState.get_substep`.

This matters for partial runs: selecting one substep of a step marks that step
`done`, and the substeps you did not select must not claim they ran.

## Where the UI takes its status from

`project_payload` derives each badge from the persisted record above, plus the
report on disk. While a run is in flight the live job snapshot overrides it —
that is how a step turns "running" then "done" without a reload — but **only
while the job is in flight**. Once a job reaches a terminal status its snapshot
stays around for the log panel and stops painting badges, so a refresh after the
output folder is deleted shows what is actually there.

## Related

- [`docs/project-config.md`](project-config.md) — the project folder, and the
  slug ↔ step-type split that decides these file names.
