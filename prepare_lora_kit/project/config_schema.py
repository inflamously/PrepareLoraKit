"""Curated, UI-editable config field schemas for pipeline steps.

Each step type maps to an ordered list of :class:`FieldSpec` describing the
user-facing tunables to surface in the frontend config strip. The schema is
intentionally *curated* — legacy, deprecated, and internal fields on the
underlying config dataclasses (``project/configs/*.py``) are omitted.

The frontend renders one control per :class:`FieldSpec`; submitted overrides are
applied back onto the step's config via :func:`apply_overrides`, which coerces
values to their Python types and re-runs the dataclass ``__post_init__``
validation (raising ``ValueError`` on invalid input).
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FieldSpec:
    """UI metadata for a single editable config field."""

    name: str
    label: str
    control: str  # "select" | "number" | "text" | "checkbox"
    value_type: str = "str"  # "str" | "int" | "float" | "bool"
    options: list[dict[str, str]] = field(default_factory=list)  # [{value,label}]
    allow_custom: bool = False  # select may accept a free-text value not in options
    nullable: bool = False  # empty input coerces to None instead of being skipped
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    placeholder: str = ""
    help: str = ""


def _select(name, label, choices, **kw) -> FieldSpec:
    options = [
        {"value": value, "label": text}
        for value, text in choices
    ]
    return FieldSpec(name=name, label=label, control="select", options=options, **kw)


def _number(name, label, value_type="float", **kw) -> FieldSpec:
    return FieldSpec(name=name, label=label, control="number", value_type=value_type, **kw)


def _check(name, label, **kw) -> FieldSpec:
    return FieldSpec(name=name, label=label, control="checkbox", value_type="bool", **kw)


def _text(name, label, **kw) -> FieldSpec:
    return FieldSpec(name=name, label=label, control="text", value_type="str", **kw)


_CAPTION_MODELS = [
    ("Qwen/Qwen2.5-VL-3B-Instruct", "Qwen2.5-VL 3B"),
    ("Qwen/Qwen2.5-VL-7B-Instruct", "Qwen2.5-VL 7B"),
    ("Qwen/Qwen2-VL-7B-Instruct", "Qwen2-VL 7B"),
]


CONFIG_FIELD_SCHEMA: dict[str, list[FieldSpec]] = {
    "ImportStep": [],
    "QualityGateStep": [
        _check("manual_review", "Manual review"),
        _check("auto_only", "Auto only (skip manual review)"),
        _check("manual_all", "Review every image"),
    ],
    "CurateStep": [
        _number("dedup_hamming_distance", "Dedup hamming distance", "int", minimum=0, step=1),
        _number("occlusion_threshold", "Occlusion threshold", "float", minimum=0, maximum=1, step=0.05),
        _check("skip_clip", "Skip CLIP coverage"),
        _text("clip_model_id", "CLIP model id", placeholder="openai/clip-vit-base-patch32"),
        _number("pca_umap_switch_threshold", "PCA→UMAP switch", "int", minimum=0, step=1),
    ],
    "UpscaleStep": [
        _select("upscale_model", "Upscale model", [
            ("seedvr2", "SeedVR2"), ("lanczos", "Lanczos"), ("custom", "Custom"),
        ]),
        _number("upscale_target", "Target side (px)", "int", minimum=1, step=64),
        _number("hallucination_ssim_threshold", "Hallucination SSIM", "float", minimum=0, maximum=1, step=0.05),
        _text("seedvr2_dit_model", "SeedVR2 DiT model", nullable=True,
              placeholder="seedvr2_ema_3b_fp8_e4m3fn.safetensors"),
        _select("seedvr2_model_residency", "SeedVR2 residency", [
            ("auto", "Auto"), ("gpu", "GPU"), ("cpu", "CPU"),
        ]),
        _number("seedvr2_batch_size", "SeedVR2 batch size", "int", minimum=1, step=1),
    ],
    "VaeGateStep": [
        _number("diff_amplification", "Diff amplification", "float", minimum=0, step=0.5),
        _number("gaussian_blur_sigma", "Gaussian blur sigma", "float", minimum=0, step=0.1),
        _number("gaussian_blur_kernel", "Gaussian blur kernel (odd)", "int", minimum=1, step=2),
        _check("otsu_enabled", "Otsu thresholding"),
        _number("outlier_sigma", "Outlier sigma", "float", minimum=0, step=0.1),
        _number("hf_cutoff_fraction", "HF cutoff fraction", "float", minimum=0, maximum=0.5, step=0.01),
        _number("max_side", "Max side (px)", "int", minimum=1, step=64, nullable=True,
                placeholder="network default"),
        _number("seed", "Seed", "int", step=1),
    ],
    "CaptionStep": [
        _select("caption_model_id", "Caption model", _CAPTION_MODELS, allow_custom=True, nullable=True,
                placeholder="Hugging Face model id"),
        _select("caption_model_task", "Caption task", [
            ("auto", "Auto"),
            ("image-text-to-text", "Image + text to text"),
            ("image-to-text", "Image to text"),
        ]),
        _select("vram_tier", "VRAM tier", [
            ("auto", "Auto"),
            ("low", "Low (≤16 GB, 4-bit)"),
            ("mid", "Mid (≤24 GB, 8-bit)"),
            ("high", "High (≤32 GB)"),
            ("max", "Max (≥32 GB)"),
        ]),
        _number("max_new_tokens", "Max new tokens", "int", minimum=1, step=10),
        _number("spot_check_pct", "Spot check fraction", "float", minimum=0, maximum=1, step=0.05),
    ],
    "AuditStep": [
        _number("min_caption", "Min caption length", "int", minimum=0, step=1),
        _number("max_caption", "Max caption length", "int", minimum=1, step=10),
        _check("check_pairing", "Check pairing"),
        _check("check_corrupt", "Check corrupt files"),
        _check("check_caption_length", "Check caption length"),
        _check("check_resolution_gate", "Check resolution gate"),
    ],
    "ConfigGenStep": [
        _text("base_template_path", "Base template path", nullable=True,
              placeholder="configs/templates/flux_base.yaml"),
    ],
    "BucketDryRunStep": [
        _number("thin_threshold", "Thin bucket threshold", "int", minimum=0, step=1),
        _check("cache_mode", "Write cache_info.json"),
    ],
}


def has_schema(step_type: str) -> bool:
    """Return True when the step exposes editable tunables (i.e. should pause)."""

    return bool(CONFIG_FIELD_SCHEMA.get(step_type))


def schema_payload(step_type: str) -> list[dict[str, Any]]:
    """Return the JSON-able field schema for a step type."""

    return [dataclasses.asdict(spec) for spec in CONFIG_FIELD_SCHEMA.get(step_type, ())]


def _coerce(spec: FieldSpec, raw: Any) -> tuple[bool, Any]:
    """Coerce a raw override to its field type. Returns (apply?, value)."""

    if spec.control == "checkbox":
        return True, bool(raw)

    is_blank = raw is None or (isinstance(raw, str) and raw.strip() == "")
    if is_blank:
        # Empty input: clear nullable fields, otherwise leave the default in place.
        return (True, None) if spec.nullable else (False, None)

    if spec.control == "number":
        try:
            return (True, int(raw)) if spec.value_type == "int" else (True, float(raw))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{spec.label}: expected a number, got {raw!r}") from exc

    return True, str(raw).strip()


def apply_overrides(step_type: str, config: Any, overrides: dict[str, Any] | None) -> Any:
    """Apply UI overrides onto a step config, validating via the dataclass.

    Unknown keys (not in the curated schema) are ignored. Coerced values are
    applied with :func:`dataclasses.replace`, which re-runs ``__post_init__`` so
    invalid combinations raise ``ValueError``.
    """

    if not overrides:
        return config

    specs = {spec.name: spec for spec in CONFIG_FIELD_SCHEMA.get(step_type, ())}
    changes: dict[str, Any] = {}
    for name, raw in overrides.items():
        spec = specs.get(name)
        if spec is None:
            continue
        apply, value = _coerce(spec, raw)
        if apply:
            changes[name] = value

    if not changes:
        return config
    return dataclasses.replace(config, **changes)
