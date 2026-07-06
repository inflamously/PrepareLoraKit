from prepare_lora_kit_pipeline.configs import ImportConfig, QualityGateConfig, CurateConfig, UpscaleConfig, \
    CaptionBboxConfig, VaeGateConfig, AuditConfig, BucketPoolsCheckConfig, ExportConfig

STEP_TYPE_MAP: dict[str, type] = {
    "ImportStep": ImportConfig,
    "QualityGateStep": QualityGateConfig,
    "CurateStep": CurateConfig,
    "UpscaleStep": UpscaleConfig,
    "CaptionBboxStep": CaptionBboxConfig,
    "VaeGateStep": VaeGateConfig,
    "AuditStep": AuditConfig,
    "BucketPoolsCheckStep": BucketPoolsCheckConfig,
    "ExportStep": ExportConfig,
}

# Visual workflow order from docs/prepare_lora_kit_dataset_workflow.excalidraw.
STEP_ORDER = tuple(STEP_TYPE_MAP)

# Direct dependency graph. Runtime selection validation also preserves visual
# order for selected steps; Export intentionally only requires Import.
STEP_PREREQUISITES: dict[str, list[str]] = {
    "QualityGateStep": ["ImportStep"],
    "CurateStep": ["QualityGateStep"],
    "UpscaleStep": ["ImportStep"],
    "CaptionBboxStep": ["QualityGateStep", "CurateStep"],
    "VaeGateStep": ["ImportStep"],
    "AuditStep": ["VaeGateStep"],
    "BucketPoolsCheckStep": ["AuditStep"],
    "ExportStep": ["ImportStep"],
}

STEP_ORDER_INDEX = {step_type: index for index, step_type in enumerate(STEP_ORDER)}

# Optional steps are not selected by default in the UI. Export can run as soon as
# Import is complete, even when no image-changing step has been run.
OPTIONAL_STEP_TYPES = {"UpscaleStep", "ExportStep"}

# Steps that manage their own per-image resume/idempotency and therefore must not
# be skipped by ``state.is_done`` on a re-run. They always re-enter ``run()`` and
# self-determine pending work (e.g. CaptionBboxStep only re-prompts uncaptioned images),
# so re-running them without ``--force`` resumes instead of redoing everything.
RESUME_AWARE_STEP_TYPES = {"VaeGateStep", "CaptionBboxStep"}
