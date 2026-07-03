from prepare_lora_kit_pipeline.configs import ImportConfig, QualityGateConfig, CurateConfig, UpscaleConfig, \
    CaptionConfig, VaeGateConfig, AuditConfig, ConfigGenConfig, BucketDryRunConfig, ExportConfig

STEP_TYPE_MAP: dict[str, type] = {
    "ImportStep": ImportConfig,
    "QualityGateStep": QualityGateConfig,
    "CurateStep": CurateConfig,
    "UpscaleStep": UpscaleConfig,
    "CaptionStep": CaptionConfig,
    "VaeGateStep": VaeGateConfig,
    "AuditStep": AuditConfig,
    "ConfigGenStep": ConfigGenConfig,
    "BucketDryRunStep": BucketDryRunConfig,
    "ExportStep": ExportConfig,
}

# Defines the order steps are ran in the pipeline down
STEP_ORDER = tuple(STEP_TYPE_MAP)

STEP_PREREQUISITES: dict[str, list[str]] = {
    "QualityGateStep": ["ImportStep"],
    "CurateStep": ["QualityGateStep"],
    "UpscaleStep": ["CurateStep"],
    "CaptionStep": ["CurateStep"],
    "VaeGateStep": [],
    "AuditStep": ["CaptionStep"],
    "ConfigGenStep": ["AuditStep"],
    "BucketDryRunStep": ["ConfigGenStep"],
    "ExportStep": ["CaptionStep"],
}

STEP_ORDER_INDEX = {step_type: index for index, step_type in enumerate(STEP_ORDER)}

# ExportStep is opt-in: it is never inserted into a default project pipeline and
# is skipped by prerequisite validation when absent. Add it explicitly to a
# project's pipeline (last) to hand the finalized dataset off to a train folder.
OPTIONAL_STEP_TYPES = {"UpscaleStep", "ExportStep"}

# Steps that manage their own per-image resume/idempotency and therefore must not
# be skipped by ``state.is_done`` on a re-run. They always re-enter ``run()`` and
# self-determine pending work (e.g. CaptionStep only re-prompts uncaptioned images),
# so re-running them without ``--force`` resumes instead of redoing everything.
RESUME_AWARE_STEP_TYPES = {"CaptionStep"}
