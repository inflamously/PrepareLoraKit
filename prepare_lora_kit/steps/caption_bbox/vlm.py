"""Generic Hugging Face caption runtime for CaptionBboxStep."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
import threading

from prepare_lora_kit.steps.caption_bbox import prompts as cap_utils
from prepare_lora_kit.report import reporter

CaptionStatusCallback = Callable[[dict[str, Any]], None]

# Cache keyed by model/task/loading settings so repeated region/full-image
# captions in one run reuse the same HF objects.
_CACHE: dict[tuple, "LoadedCaptionModel"] = {}

# Pixel budget (area) applied before processor input. Visual token count scales
# with area, so this is the first line of defense against activation OOM.
_DEFAULT_MAX_PIXELS = 1024 * 1024

# Region-crop default prompt lives in prompts.py (single source of truth shared
# with the UI prompt-library "Default"); re-exported here for the caption_region path.
_REGION_PROMPT = cap_utils._REGION_PROMPT

_TASKS = {"auto", "image-text-to-text", "image-to-text"}


@dataclass
class LoadedCaptionModel:
    model: Any
    processor: Any
    adapter: str
    supports_prompt: bool
    quantization: str
    dtype: str
    device: str
    max_pixels: int


def _bitsandbytes_available() -> bool:
    try:
        import bitsandbytes  # noqa: F401
        return True
    except Exception:
        return False


def _cuda_total_vram_gb(torch) -> float:
    try:
        props = torch.cuda.get_device_properties(0)
        return float(props.total_memory) / (1024 ** 3)
    except Exception:
        return 0.0


def _cuda_free_vram_gb(torch) -> float:
    try:
        free, _total = torch.cuda.mem_get_info()
        return float(free) / (1024 ** 3)
    except Exception:
        return 0.0


def _resolve_quantization(quantization: str, torch) -> str:
    quantization = str(quantization or "auto").strip().lower()
    if quantization not in {"auto", "none", "4bit", "8bit"}:
        raise ValueError(f"Unsupported caption quantization: {quantization}")
    if quantization in {"4bit", "8bit"}:
        if not torch.cuda.is_available():
            raise RuntimeError(f"{quantization} caption loading requires CUDA.")
        if not _bitsandbytes_available():
            raise RuntimeError(
                f"{quantization} caption loading requires bitsandbytes; install/fix bitsandbytes or choose Auto/Unquantized."
            )
        return quantization
    if quantization != "auto":
        return quantization
    if not torch.cuda.is_available():
        return "none"
    if not _bitsandbytes_available():
        reporter.warn("bitsandbytes unavailable; auto VLM quantization selecting unquantized CPU/GPU load.")
        return "none"
    total_gb = _cuda_total_vram_gb(torch)
    if total_gb and total_gb <= 16:
        return "4bit"
    if not total_gb or total_gb <= 32:
        return "8bit"
    return "none"


def _load(model_id: str, task: str, quantization: str, dtype: str, max_pixels: int) -> LoadedCaptionModel:
    import torch

    task = str(task or "auto").strip().lower()
    if task not in _TASKS:
        raise ValueError(f"Unsupported caption_model_task: {task}")

    resolved_quantization = _resolve_quantization(quantization, torch)
    resolved_dtype = _resolve_dtype(dtype, torch)
    key = (model_id, task, resolved_quantization, str(resolved_dtype), max_pixels)
    if key in _CACHE:
        return _CACHE[key]

    from transformers import AutoProcessor

    model_kwargs = _model_kwargs(resolved_quantization, resolved_dtype)
    errors: list[str] = []

    if task in {"auto", "image-text-to-text"}:
        try:
            processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
            if not hasattr(processor, "apply_chat_template"):
                raise RuntimeError("processor has no chat template")
            model = _load_prompted_model(model_id, model_kwargs)
            loaded = LoadedCaptionModel(
                model=model,
                processor=processor,
                adapter="image-text-to-text",
                supports_prompt=True,
                quantization=resolved_quantization,
                dtype=str(resolved_dtype).replace("torch.", ""),
                device=str(_input_device(model)),
                max_pixels=max_pixels,
            )
            model.eval()
            _CACHE[key] = loaded
            return loaded
        except Exception as exc:
            errors.append(f"image-text-to-text: {exc}")
            _clear_cuda(torch)

    if task in {"auto", "image-to-text"}:
        try:
            processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
            model = _load_image_to_text_model(model_id, model_kwargs)
            loaded = LoadedCaptionModel(
                model=model,
                processor=processor,
                adapter="image-to-text",
                supports_prompt=False,
                quantization=resolved_quantization,
                dtype=str(resolved_dtype).replace("torch.", ""),
                device=str(_input_device(model)),
                max_pixels=max_pixels,
            )
            model.eval()
            _CACHE[key] = loaded
            return loaded
        except Exception as exc:
            errors.append(f"image-to-text: {exc}")
            _clear_cuda(torch)

    raise RuntimeError(
        f"Could not load caption model '{model_id}' with supported Hugging Face adapters:\n  "
        + "\n  ".join(errors)
    )


def _resolve_dtype(dtype: str, torch):
    torch_dtype = getattr(torch, str(dtype or "bfloat16"), torch.bfloat16)
    if not torch.cuda.is_available():
        return torch.float32
    return torch_dtype


def _model_kwargs(quantization: str, torch_dtype) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "torch_dtype": torch_dtype,
        "device_map": "auto",
        "low_cpu_mem_usage": True,
    }
    if quantization in {"4bit", "8bit"}:

        from transformers import BitsAndBytesConfig
        if quantization == "4bit":
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch_dtype,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )
        else:
            kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        kwargs.pop("torch_dtype", None)
    return kwargs


def _load_prompted_model(model_id: str, model_kwargs: dict[str, Any]):
    errors = []
    for class_name in (
            "AutoModelForImageTextToText",
            "AutoModelForVision2Seq",
            "Qwen2VLForConditionalGeneration",
    ):
        try:
            import transformers

            cls = getattr(transformers, class_name)
            return cls.from_pretrained(model_id, trust_remote_code=True, **model_kwargs)
        except Exception as exc:
            errors.append(f"{class_name}: {exc}")
    raise RuntimeError("; ".join(errors))


def _load_image_to_text_model(model_id: str, model_kwargs: dict[str, Any]):
    errors = []
    for class_name in (
            "AutoModelForVision2Seq",
            "BlipForConditionalGeneration",
            "VisionEncoderDecoderModel",
            "AutoModelForCausalLM",
    ):
        try:
            import transformers

            cls = getattr(transformers, class_name)
            return cls.from_pretrained(model_id, trust_remote_code=True, **model_kwargs)
        except Exception as exc:
            errors.append(f"{class_name}: {exc}")
    raise RuntimeError("; ".join(errors))


def _downscale(img, max_pixels: int):
    from PIL import Image

    w, h = img.size
    if w * h > max_pixels:
        scale = (max_pixels / (w * h)) ** 0.5
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    return img


def _load_image(image_path: Path, max_pixels: int):
    from PIL import Image

    return _downscale(Image.open(image_path).convert("RGB"), max_pixels)


def _input_device(model):
    try:
        return next(model.parameters()).device
    except Exception:
        pass
    try:
        return next(model.buffers()).device
    except Exception:
        pass
    try:
        return model.device
    except Exception:
        pass

    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def _to_device(inputs: dict[str, Any], device: Any) -> dict[str, Any]:
    return {k: v.to(device) if hasattr(v, "to") else v for k, v in inputs.items()}


def _run_prompted(loaded: LoadedCaptionModel, image, prompt_text: str, max_new_tokens: int) -> str:
    import torch

    processor = loaded.processor
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt_text},
            ],
        }
    ]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text], images=[image], return_tensors="pt")
    device = _input_device(loaded.model)
    inputs = _to_device(inputs, device)

    try:
        with torch.no_grad():
            out = loaded.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                temperature=None,
                top_p=None,
            )
        input_len = inputs["input_ids"].shape[1]
        generated = processor.decode(out[0][input_len:], skip_special_tokens=True)
    finally:
        del inputs
        _clear_cuda(torch)

    return cap_utils.strip_boilerplate(generated.strip())


def _run_image_to_text(loaded: LoadedCaptionModel, image, max_new_tokens: int) -> str:
    import torch

    processor = loaded.processor
    model_id = str(getattr(loaded.model, "name_or_path", "") or "")
    text_prompt = _image_to_text_prompt(model_id)
    processor_kwargs: dict[str, Any] = {"images": image, "return_tensors": "pt"}
    if text_prompt:
        processor_kwargs["text"] = text_prompt
    inputs = processor(**processor_kwargs)
    device = _input_device(loaded.model)
    inputs = _to_device(inputs, device)

    try:
        with torch.no_grad():
            out = loaded.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        generated = processor.decode(out[0], skip_special_tokens=True)
        if hasattr(processor, "post_process_generation") and text_prompt:
            try:
                parsed = processor.post_process_generation(
                    generated,
                    task=text_prompt,
                    image_size=image.size,
                )
                generated = _first_caption_value(parsed) or generated
            except Exception:
                pass
    finally:
        del inputs
        _clear_cuda(torch)

    return cap_utils.strip_boilerplate(generated.strip())


def _image_to_text_prompt(model_id: str) -> str:
    if "florence" in model_id.lower():
        return "<MORE_DETAILED_CAPTION>"
    return ""


def _first_caption_value(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for item in value.values():
            found = _first_caption_value(item)
            if found:
                return found
    if isinstance(value, (list, tuple)):
        for item in value:
            found = _first_caption_value(item)
            if found:
                return found
    return None


def _compose_classic_caption(base_caption: str, annotations: list[dict], concept_token: str | None) -> str:
    caption = cap_utils.strip_boilerplate(base_caption)
    labels = []
    for ann in annotations:
        label = str(ann.get("label") or "").strip()
        if label:
            labels.append(label)
    if labels:
        unique_labels = list(dict.fromkeys(labels))
        detail = ", ".join(unique_labels)
        caption = f"{caption}, with {detail}" if caption else detail
    if concept_token and caption and not cap_utils.token_present(caption, concept_token):
        caption = f"{concept_token}, {caption}"
    return cap_utils.strip_boilerplate(caption)


def _clear_cuda(torch) -> None:
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


class CaptionRuntime:
    """Reusable Hugging Face caption runtime for one captioning step."""

    def __init__(
            self,
            model_id: str,
            *,
            task: str = "auto",
            quantization: str = "none",
            dtype: str = "bfloat16",
            max_pixels: int = _DEFAULT_MAX_PIXELS,
            status_callback: CaptionStatusCallback | None = None,
            caption_prompt: str | None = None,
            region_prompt: str | None = None,
    ) -> None:
        self.model_id = str(model_id or "").strip()
        self.task = task
        self.quantization = quantization
        self.dtype = dtype
        self.max_pixels = max_pixels
        # Optional custom prompt templates from the global prompt library; when
        # unset, the built-in full-image / region defaults are used.
        self.caption_prompt = caption_prompt or None
        self.region_prompt = region_prompt or None
        self._loaded: LoadedCaptionModel | None = None
        self._lock = threading.Lock()
        self._status_callback = status_callback
        self._status: dict[str, Any] = {}

    @property
    def metadata(self) -> dict[str, Any]:
        if self._loaded is None:
            return {
                "model_id": self.model_id,
                "task": self.task,
                "adapter": None,
                "device": None,
                "quantization": self.quantization,
                "dtype": self.dtype,
                "max_pixels": self.max_pixels,
            }
        return {
            "model_id": self.model_id,
            "task": self.task,
            "adapter": self._loaded.adapter,
            "device": self._loaded.device,
            "quantization": self._loaded.quantization,
            "dtype": self._loaded.dtype,
            "max_pixels": self._loaded.max_pixels,
        }

    @property
    def status(self) -> dict[str, Any]:
        return dict(self._status)

    def load(self) -> None:
        if self._loaded is not None:
            return
        if not self.model_id:
            raise RuntimeError("CaptionBboxStep requires caption_model_id before captioning can run.")
        self._emit_status("loading", f"Loading caption model {self.model_id}")
        import torch

        reporter.info(
            "Caption model load: "
            f"{self.model_id} (task={self.task}, quant={self.quantization}, dtype={self.dtype}, "
            f"cuda={torch.cuda.is_available()}, total_vram_gb={_cuda_total_vram_gb(torch):.1f}, "
            f"free_vram_gb={_cuda_free_vram_gb(torch):.1f}, max_pixels={self.max_pixels})"
        )
        try:
            self._loaded = _load(
                self.model_id,
                self.task,
                self.quantization,
                self.dtype,
                self.max_pixels,
            )
        except Exception as exc:
            self._emit_status("failed", f"Caption model failed to load: {exc}", error=str(exc))
            raise
        self._emit_status(
            "ready",
            f"Caption model ready: {self.model_id} ({self._loaded.adapter}, {self._loaded.device})",
        )
        reporter.info(
            "Caption model ready: "
            f"adapter={self._loaded.adapter}, device={self._loaded.device}, "
            f"quant={self._loaded.quantization}, dtype={self._loaded.dtype}"
        )

    def unload(self) -> None:
        self._loaded = None
        unload()
        self._emit_status("unloaded", "Caption model unloaded")

    def _run(self, image, prompt_text: str, max_new_tokens: int) -> str:
        with self._lock:
            self.load()
            assert self._loaded is not None
            if self._loaded.supports_prompt:
                return _run_prompted(self._loaded, image, prompt_text, max_new_tokens)
            return _run_image_to_text(self._loaded, image, max_new_tokens)

    def caption_image(
            self,
            image_path: Path,
            annotations: list[dict],
            concept_token: str | None,
            *,
            max_new_tokens: int = 200,
    ) -> str:
        self._emit_status("captioning", f"Captioning {Path(image_path).name}", current_image=str(image_path))
        ann_lines = []
        for ann in annotations:
            x1, y1, x2, y2 = ann["x1"], ann["y1"], ann["x2"], ann["y2"]
            region_desc = cap_utils.describe_box_position(x1, y1, x2, y2)
            ann_lines.append({
                "label": ann["label"],
                "region_desc": region_desc,
                "crop_name": ann.get("crop_name", ""),
            })

        prompt_text = cap_utils.build_full_image_prompt(
            ann_lines, concept_token, template=self.caption_prompt
        )
        image = _load_image(image_path, self.max_pixels)
        try:
            text = self._run(image, prompt_text, max_new_tokens)
            if self._loaded is not None and not self._loaded.supports_prompt:
                text = _compose_classic_caption(text, annotations, concept_token)
            self._emit_status("ready", f"Caption model ready: {self.model_id}")
            return text
        except Exception as exc:
            self._emit_status("failed", f"Captioning failed for {Path(image_path).name}: {exc}", error=str(exc))
            raise

    def caption_region(
            self,
            image,
            *,
            max_new_tokens: int = 80,
    ) -> str:
        self._emit_status("captioning", "Captioning selected region")
        if isinstance(image, (str, Path)):
            img = _load_image(Path(image), self.max_pixels)
        else:
            img = _downscale(image.convert("RGB"), self.max_pixels)
        # Region crops carry no bbox annotations; the concept token is applied to
        # the crop caption afterwards (see artifacts._save_bbox_training_item), so
        # the {concept_token} placeholder resolves to empty here.
        region_prompt = (
            cap_utils.apply_prompt_placeholders(self.region_prompt, "", None)
            if self.region_prompt
            else _REGION_PROMPT
        )
        try:
            text = self._run(img, region_prompt, max_new_tokens)
            self._emit_status("ready", f"Caption model ready: {self.model_id}")
            return text
        except Exception as exc:
            self._emit_status("failed", f"Region captioning failed: {exc}", error=str(exc))
            raise

    def _emit_status(self, phase: str, message: str, **extra: Any) -> None:
        payload = {
            "phase": phase,
            "message": message,
            **self.metadata,
            **extra,
        }
        self._status = payload
        if self._status_callback is not None:
            self._status_callback(payload)


def caption_image(
        image_path: Path,
        annotations: list[dict],
        concept_token: str | None,
        model_id: str,
        *,
        task: str = "auto",
        quantization: str = "none",
        dtype: str = "bfloat16",
        max_new_tokens: int = 200,
        max_pixels: int = _DEFAULT_MAX_PIXELS,
) -> str:
    runtime = CaptionRuntime(
        model_id,
        task=task,
        quantization=quantization,
        dtype=dtype,
        max_pixels=max_pixels,
    )
    return runtime.caption_image(image_path, annotations, concept_token, max_new_tokens=max_new_tokens)


def caption_region(
        image,
        model_id: str,
        *,
        task: str = "auto",
        quantization: str = "none",
        dtype: str = "bfloat16",
        max_new_tokens: int = 80,
        max_pixels: int = _DEFAULT_MAX_PIXELS,
) -> str:
    runtime = CaptionRuntime(
        model_id,
        task=task,
        quantization=quantization,
        dtype=dtype,
        max_pixels=max_pixels,
    )
    return runtime.caption_region(image, max_new_tokens=max_new_tokens)


def unload() -> None:
    """Drop cached caption models and free VRAM."""
    import torch

    _CACHE.clear()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
