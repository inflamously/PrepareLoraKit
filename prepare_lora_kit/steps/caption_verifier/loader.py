"""diffusers pipeline construction for CaptionVerifierStep.

Every ``torch``/``diffusers``/``transformers`` import is function-local:
``tests/steps/test_imports.py`` imports every module under ``steps/``, and the
config schema imports this package's :mod:`.catalog`.

Quantization goes through diffusers' :class:`PipelineQuantizationConfig`, which
applies the right backend to each named component (diffusers' own
``BitsAndBytesConfig`` for the denoiser, transformers' for the text encoder).
That is what makes a 9B FLUX.2 klein plus its Qwen3 text encoder fit a 16 GB
card, and it avoids hand-wiring two same-named config classes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from prepare_lora_kit.report import reporter
from prepare_lora_kit.steps.caption_verifier.plan import GenerationPlan

_SINGLE_FILE_SUFFIXES = (".safetensors", ".ckpt", ".pt", ".bin")
_FALLBACK_CLASSES = ("AutoPipelineForText2Image", "DiffusionPipeline")


def load_pipeline(plan: GenerationPlan) -> Any:
    """Build, place and memory-tune a text-to-image pipeline for ``plan``."""
    import torch  # noqa: F401  (imported for dtype resolution below)
    import diffusers

    pipeline_cls = _resolve_pipeline_cls(diffusers, plan)
    pipe = _instantiate_pipeline(diffusers, pipeline_cls, plan)
    _apply_placement(pipe, plan)
    _apply_memory_savers(pipe)
    return pipe


def _resolve_pipeline_cls(diffusers, plan: GenerationPlan):
    """Named class -> auto pipeline -> DiffusionPipeline.

    A catalog model whose class is missing gets an actionable version error
    rather than a confusing failure deep inside ``from_pretrained``.
    """
    named = getattr(diffusers, plan.pipeline_cls, None)
    if named is not None:
        return named

    if plan.pipeline_cls not in _FALLBACK_CLASSES:
        installed = getattr(diffusers, "__version__", "unknown")
        raise RuntimeError(
            f"{plan.pipeline_cls} is not available in the installed diffusers "
            f"({installed}); {plan.model_id} needs diffusers >= "
            f"{plan.min_diffusers}. Upgrade diffusers or pick another model."
        )

    for name in _FALLBACK_CLASSES:
        candidate = getattr(diffusers, name, None)
        if candidate is not None:
            return candidate
    raise RuntimeError(  # pragma: no cover - diffusers always ships these
        "The installed diffusers exposes no usable text-to-image pipeline class."
    )


def _instantiate_pipeline(diffusers, pipeline_cls, plan: GenerationPlan):
    """Handle the three model-id forms, mirroring ``vae_gate/vae._instantiate_vae``.

    * ``repo_id::path/in/repo.safetensors`` -> download then ``from_single_file``
    * a path/URL ending in a checkpoint suffix -> ``from_single_file``
    * anything else -> ``from_pretrained``
    """
    kwargs = _from_pretrained_kwargs(diffusers, plan)
    model_id = plan.model_id

    if "::" in model_id:
        from huggingface_hub import hf_hub_download

        repo_id, _, filename = model_id.partition("::")
        local = hf_hub_download(repo_id, filename)
        return _from_single_file(pipeline_cls, local, kwargs)

    if model_id.lower().endswith(_SINGLE_FILE_SUFFIXES):
        return _from_single_file(pipeline_cls, model_id, kwargs)

    return pipeline_cls.from_pretrained(model_id, **kwargs)


def _from_single_file(pipeline_cls, path: str, kwargs: dict):
    loader = getattr(pipeline_cls, "from_single_file", None)
    if loader is None:
        raise RuntimeError(
            f"{pipeline_cls.__name__} cannot load a single checkpoint file; "
            "point the model id at a diffusers repo instead."
        )
    # Quantization config is not supported by every from_single_file path.
    single = {k: v for k, v in kwargs.items() if k != "quantization_config"}
    return loader(path, **single)


def _from_pretrained_kwargs(diffusers, plan: GenerationPlan) -> dict:
    import torch

    kwargs: dict[str, Any] = {"torch_dtype": _torch_dtype(torch, plan.dtype)}

    if plan.family == "sd15":
        # A false-positive safety trip returns a black image, which reads as
        # "the model doesn't know this term" — an actively misleading verdict.
        kwargs["safety_checker"] = None
        kwargs["requires_safety_checker"] = False

    quant = _quantization_config(diffusers, plan)
    if quant is not None:
        kwargs["quantization_config"] = quant
    return kwargs


def _quantization_config(diffusers, plan: GenerationPlan):
    if plan.quantization not in {"4bit", "8bit"} or not plan.quantize_components:
        return None

    import torch

    pipeline_quant = getattr(diffusers, "PipelineQuantizationConfig", None)
    if pipeline_quant is None:
        installed = getattr(diffusers, "__version__", "unknown")
        raise RuntimeError(
            f"{plan.quantization} loading needs diffusers with "
            f"PipelineQuantizationConfig (installed: {installed}); "
            "upgrade diffusers or choose the Max VRAM tier."
        )

    if plan.quantization == "4bit":
        backend = "bitsandbytes_4bit"
        quant_kwargs = {
            "load_in_4bit": True,
            "bnb_4bit_quant_type": "nf4",
            "bnb_4bit_use_double_quant": True,
            "bnb_4bit_compute_dtype": _torch_dtype(torch, plan.dtype),
        }
    else:
        backend = "bitsandbytes_8bit"
        quant_kwargs = {"load_in_8bit": True}

    return pipeline_quant(
        quant_backend=backend,
        quant_kwargs=quant_kwargs,
        components_to_quantize=list(plan.quantize_components),
    )


def _apply_placement(pipe, plan: GenerationPlan) -> None:
    """Install offload hooks *or* move the pipeline — never both.

    ``.to(device)`` after accelerate has installed offload hooks corrupts the
    placement, so these branches are mutually exclusive.
    """
    if plan.offload == "sequential":
        pipe.enable_sequential_cpu_offload()
        return
    if plan.offload == "model":
        pipe.enable_model_cpu_offload()
        return
    pipe.to(plan.device)


def _apply_memory_savers(pipe) -> None:
    """VAE tiling/slicing keeps decode VRAM flat regardless of resolution."""
    vae = getattr(pipe, "vae", None)
    for method in ("enable_tiling", "enable_slicing"):
        target = getattr(vae, method, None)
        if target is None:
            continue
        try:
            target()
        except Exception as exc:  # pragma: no cover - best effort
            reporter.warn(f"Caption verifier: vae.{method}() failed ({exc}).")


def _torch_dtype(torch, dtype: str):
    return {
        "float32": torch.float32,
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
    }.get(str(dtype).lower(), torch.float32)


def pipeline_device(pipe) -> str:
    """Best-effort device string for reporting."""
    device = getattr(pipe, "device", None)
    if device is not None:
        return str(device)
    for attr in ("transformer", "unet", "text_encoder"):
        module = getattr(pipe, attr, None)
        module_device = getattr(module, "device", None)
        if module_device is not None:
            return str(module_device)
    return "unknown"


def preview_dir_for(root: Path, source: Path) -> Path:
    """Per-image preview directory, mirroring ``vae_gate/review``'s scheme."""
    import hashlib

    stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in source.stem)[:48]
    digest = hashlib.sha1(str(source).encode("utf-8")).hexdigest()[:8]
    return Path(root) / f"{stem}_{digest}"
