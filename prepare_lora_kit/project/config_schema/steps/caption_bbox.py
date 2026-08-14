"""Editable config fields for CaptionBboxStep."""
from __future__ import annotations

from prepare_lora_kit.project.config_schema.fields import (
    FieldSpec,
    _number,
    _prompt,
    _select,
    _textarea,
)

STEP_TYPE = "CaptionBboxStep"

_CAPTION_MODELS = [
    ("Qwen/Qwen3.8-27B", "Qwen3.8 27B (24 GB+)"),
    ("Qwen/Qwen3-VL-2B-Instruct", "Qwen3-VL 2B"),
    ("Qwen/Qwen3-VL-4B-Instruct", "Qwen3-VL 4B"),
    ("Qwen/Qwen3-VL-8B-Instruct", "Qwen3-VL 8B"),
    ("Qwen/Qwen2.5-VL-3B-Instruct", "Qwen2.5-VL 3B"),
    ("Qwen/Qwen2.5-VL-7B-Instruct", "Qwen2.5-VL 7B"),
    ("Qwen/Qwen2-VL-7B-Instruct", "Qwen2-VL 7B"),
    ("fancyfeast/llama-joycaption-beta-one-hf-llava", "JoyCaption Beta One"),
]
# Every id above resolves to a native transformers architecture. InternVL3-8B and
# MiniCPM-V-4_5 were dropped: both declare a model_type transformers 5.x does not
# register (`internvl_chat`, `minicpmv` — the in-tree ones are `internvl`, i.e. the
# converted `-hf` checkpoints, and `minicpmv4_6`), so both fall back to Hub-authored
# code written against the 4.x API. The field still accepts a custom id, so anyone
# who wants them can type one — and will be told to opt in via
# `huggingface.allow_remote_code` rather than having it granted silently.

FIELDS: list[FieldSpec] = [
    _select("caption_model_id", "Caption model", _CAPTION_MODELS, allow_custom=True, nullable=True,
            placeholder="Hugging Face model id"),
    _select("caption_model_task", "Caption task", [
        ("auto", "Auto"),
        ("image-text-to-text", "Image + text to text"),
        ("image-to-text", "Image to text"),
    ]),
    _select("caption_strategy", "Caption strategy", [
        ("grounded", "Grounded (observe → compose → gap-fill)"),
        ("single", "Single pass (fast)"),
    ], help="Grounded composes the caption from observed facts, then fills any gap it "
            "left — for accurate, hallucination-free captions. It observes only when "
            "regions are not already annotated, and gap-fills only when the caption "
            "looks thin, so annotated images cost one pass. Single is the one-shot "
            "pass. Classic image-to-text models always use single."),
    _select("vram_tier", "VRAM tier", [
        ("auto", "Auto"),
        ("low", "Low (≤16 GB, 4-bit)"),
        ("mid", "Mid (≤24 GB, 8-bit)"),
        ("high", "High (≤32 GB)"),
        ("max", "Max (≥32 GB)"),
    ]),
    _number("max_new_tokens", "Max new tokens", "int", minimum=1, step=10),
    _number("spot_check_pct", "Spot check fraction", "float", minimum=0, maximum=1, step=0.05),
    _textarea("domain_brief", "Domain brief",
              placeholder="What is this dataset? Vocabulary, what you'll see, terms to avoid…",
              help="Authoritative context prepended to every caption prompt. Use it when "
                   "the model does not know the domain: say what the dataset depicts, "
                   "name the things it contains, and list any wrong names it should "
                   "never use. Blank = no domain context."),
    _prompt("caption_prompt", "Caption prompt",
            placeholder="Leave blank to use the built-in default prompt…",
            help="Full-image caption instruction. Supports {bbox_annotations} and "
                 "{concept_token} placeholders. Blank = built-in default."),
    _prompt("region_prompt", "Region prompt",
            placeholder="Leave blank to use the built-in region prompt…",
            help="Bbox/crop caption instruction. Supports the {region_position} "
                 "placeholder (the box's location prose when captioning in the "
                 "context of the full image; empty for a bare crop). Blank = "
                 "built-in default."),
]
