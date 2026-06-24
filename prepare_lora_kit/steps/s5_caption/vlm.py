"""
Generic vision-language captioner.

Loads ANY image-text-to-text model from the HF hub (Qwen2-VL, Qwen2.5-VL,
Qwen3-VL, LLaVA, Idefics, InternVL, …) via the `AutoModelForImageTextToText`
generic head, with fallbacks for older transformers / Qwen-only builds.

VRAM safety:
  * Images are downscaled to a pixel budget BEFORE the processor runs — native
    resolution is the #1 cause of OOM (visual-token count scales with area).
  * Optional 4-bit / 8-bit quantization via bitsandbytes.
  * CUDA cache is emptied after every generation.
"""
from __future__ import annotations
import threading
from pathlib import Path

from ...utils import caption as cap_utils
from ...utils import report as rpt

# Cache keyed by (model_id, resolved quantization, dtype) so switching models reloads.
_CACHE: dict[tuple, tuple] = {}

# Pixel budget (area) the image is downscaled to before captioning.
# ~1 MP keeps Qwen-VL visual tokens bounded (~1024 tokens) → no activation OOM.
_DEFAULT_MAX_PIXELS = 1024 * 1024

# Prompt for captioning a single cropped region (used by the bbox "Box Caption"
# button). Asks for a short, literal phrase that reads like a hand-written label.
_REGION_PROMPT = (
    "Describe what is shown in this image with a short, literal phrase — a few "
    "comma-separated words or descriptors. No full sentences, no commentary, and "
    "do not mention that this is a crop or region. Output only the description."
)


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


def _resolve_quantization(quantization: str, torch) -> str:
    if quantization != "auto":
        return quantization
    if not torch.cuda.is_available():
        return "none"
    if not _bitsandbytes_available():
        rpt.warn("bitsandbytes unavailable; auto VLM quantization falling back to unquantized load.")
        return "none"
    total_gb = _cuda_total_vram_gb(torch)
    if total_gb and total_gb <= 16:
        return "4bit"
    if not total_gb or total_gb <= 32:
        return "8bit"
    return "none"


def _load(model_id: str, quantization: str, dtype: str):
    import torch

    resolved_quantization = _resolve_quantization(quantization, torch)
    key = (model_id, resolved_quantization, dtype)
    if key in _CACHE:
        return _CACHE[key]

    from transformers import AutoProcessor

    torch_dtype = getattr(torch, dtype, torch.bfloat16)
    if not torch.cuda.is_available():
        torch_dtype = torch.float32

    model_kwargs: dict = {
        "torch_dtype": torch_dtype,
        "device_map": "auto",
        "low_cpu_mem_usage": True,
    }

    if resolved_quantization in ("4bit", "8bit") and torch.cuda.is_available():
        try:
            from transformers import BitsAndBytesConfig
            if resolved_quantization == "4bit":
                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch_dtype,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                )
            else:
                model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
            # quant config owns dtype; drop the redundant top-level one
            model_kwargs.pop("torch_dtype", None)
        except Exception as exc:
            rpt.warn(f"bitsandbytes {resolved_quantization} unavailable ({exc}); loading full precision.")

    rpt.info(f"Loading VL model: {model_id} (quant={resolved_quantization}, dtype={dtype}) …")
    model = _from_pretrained(model_id, model_kwargs)
    processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    model.eval()

    _CACHE[key] = (model, processor)
    return model, processor


def _from_pretrained(model_id: str, model_kwargs: dict):
    """Try generic VL heads first, fall back to Qwen-specific classes."""
    errors = []
    try:
        from transformers import AutoModelForImageTextToText
        return AutoModelForImageTextToText.from_pretrained(
            model_id, trust_remote_code=True, **model_kwargs)
    except Exception as exc:
        errors.append(f"AutoModelForImageTextToText: {exc}")

    try:
        from transformers import AutoModelForVision2Seq
        return AutoModelForVision2Seq.from_pretrained(
            model_id, trust_remote_code=True, **model_kwargs)
    except Exception as exc:
        errors.append(f"AutoModelForVision2Seq: {exc}")

    try:
        from transformers import Qwen2VLForConditionalGeneration
        return Qwen2VLForConditionalGeneration.from_pretrained(model_id, **model_kwargs)
    except Exception as exc:
        errors.append(f"Qwen2VLForConditionalGeneration: {exc}")

    raise RuntimeError(
        f"Could not load '{model_id}' with any known VL class:\n  " + "\n  ".join(errors)
    )


def _downscale(img, max_pixels: int):
    """Downscale a PIL image to the pixel budget. Bounds visual tokens → no OOM."""
    from PIL import Image
    w, h = img.size
    if w * h > max_pixels:
        scale = (max_pixels / (w * h)) ** 0.5
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    return img


def _load_image(image_path: Path, max_pixels: int):
    """Open + downscale to the pixel budget."""
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


def _run(model, processor, image, prompt_text: str, max_new_tokens: int) -> str:
    """Run one image+text generation and return the cleaned decoded text."""
    import torch

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
    device = _input_device(model)
    inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in inputs.items()}

    try:
        with torch.no_grad():
            out = model.generate(
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
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    return cap_utils.strip_boilerplate(generated.strip())


class CaptionRuntime:
    """Reusable VLM runtime for one captioning step."""

    def __init__(
        self,
        model_id: str = "Qwen/Qwen2-VL-7B-Instruct",
        *,
        quantization: str = "none",
        dtype: str = "bfloat16",
        max_pixels: int = _DEFAULT_MAX_PIXELS,
    ) -> None:
        self.model_id = model_id
        self.quantization = quantization
        self.dtype = dtype
        self.max_pixels = max_pixels
        self._model = None
        self._processor = None
        self._lock = threading.Lock()

    def load(self) -> None:
        if self._model is not None and self._processor is not None:
            return
        self._model, self._processor = _load(self.model_id, self.quantization, self.dtype)

    def unload(self) -> None:
        self._model = None
        self._processor = None
        unload()

    def _run(self, image, prompt_text: str, max_new_tokens: int) -> str:
        with self._lock:
            self.load()
            return _run(self._model, self._processor, image, prompt_text, max_new_tokens)

    def caption_image(
        self,
        image_path: Path,
        annotations: list[dict],
        concept_token: str | None,
        *,
        max_new_tokens: int = 200,
    ) -> str:
        ann_lines = []
        for ann in annotations:
            x1, y1, x2, y2 = ann["x1"], ann["y1"], ann["x2"], ann["y2"]
            region_desc = f"top-left ({x1:.2f},{y1:.2f}) to bottom-right ({x2:.2f},{y2:.2f})"
            ann_lines.append({
                "label": ann["label"],
                "region_desc": region_desc,
                "crop_name": ann.get("crop_name", ""),
            })

        prompt_text = cap_utils.build_bfl_prompt(ann_lines, concept_token)
        image = _load_image(image_path, self.max_pixels)
        return self._run(image, prompt_text, max_new_tokens)

    def caption_region(
        self,
        image,
        *,
        max_new_tokens: int = 80,
    ) -> str:
        """
        Caption a single cropped region. `image` is a PIL.Image (a crop) or a path.
        Returns a short phrase suitable for dropping straight into a bbox label.
        """
        if isinstance(image, (str, Path)):
            img = _load_image(Path(image), self.max_pixels)
        else:
            img = _downscale(image.convert("RGB"), self.max_pixels)
        return self._run(img, _REGION_PROMPT, max_new_tokens)


def caption_image(
    image_path: Path,
    annotations: list[dict],
    concept_token: str | None,
    model_id: str = "Qwen/Qwen2-VL-7B-Instruct",
    *,
    quantization: str = "none",
    dtype: str = "bfloat16",
    max_new_tokens: int = 200,
    max_pixels: int = _DEFAULT_MAX_PIXELS,
) -> str:
    runtime = CaptionRuntime(
        model_id,
        quantization=quantization,
        dtype=dtype,
        max_pixels=max_pixels,
    )
    return runtime.caption_image(image_path, annotations, concept_token, max_new_tokens=max_new_tokens)


def caption_region(
    image,
    model_id: str = "Qwen/Qwen2-VL-7B-Instruct",
    *,
    quantization: str = "none",
    dtype: str = "bfloat16",
    max_new_tokens: int = 80,
    max_pixels: int = _DEFAULT_MAX_PIXELS,
) -> str:
    """
    Caption a single cropped region. `image` is a PIL.Image (a crop) or a path.
    Returns a short phrase suitable for dropping straight into a bbox label.
    """
    runtime = CaptionRuntime(
        model_id,
        quantization=quantization,
        dtype=dtype,
        max_pixels=max_pixels,
    )
    return runtime.caption_region(image, max_new_tokens=max_new_tokens)


def unload() -> None:
    """Drop the cached model and free VRAM."""
    import torch
    _CACHE.clear()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
