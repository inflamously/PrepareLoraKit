"""
Step 5 — Caption with Bbox Annotation + Qwen3-VL BFL-structured captioning

For each image:
  1. Open a tkinter bbox-draw canvas (Ideogram-4-style region annotation).
  2. User draws boxes and labels each region.
  3. Bbox context + image are sent to Qwen3-VL to produce a BFL-structured caption.
  4. Caption is cleaned, token-checked, and saved as {stem}.txt.
"""
from __future__ import annotations
import random
from pathlib import Path

from ..utils import image as img_utils
from ..utils import caption as cap_utils
from ..utils import report as rpt

_BOX_COLOURS = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c"]


# ── Bbox annotation UI (tkinter) ──────────────────────────────────────────────

class _BboxAnnotator:
    """
    Opens a tkinter window for the given image.
    User draws bounding boxes by click-drag; clicks on a completed box to add a label.
    Returns list of {x1,y1,x2,y2,label} in normalised [0,1] coords.
    """

    def __init__(self, image_path: Path, max_w: int = 1100, max_h: int = 750):
        import tkinter as tk
        from PIL import Image, ImageTk

        self._path = image_path
        self._result: list[dict] | None = None
        self._skipped = False

        pil = Image.open(image_path).convert("RGB")
        iw, ih = pil.size
        scale = min(max_w / iw, max_h / ih, 1.0)
        disp_w = int(iw * scale)
        disp_h = int(ih * scale)
        self._scale = scale
        self._img_w, self._img_h = iw, ih

        pil_disp = pil.resize((disp_w, disp_h), Image.LANCZOS)

        self._root = tk.Tk()
        self._root.title(f"Step 5 — Annotate: {image_path.name}")

        self._tk_img = ImageTk.PhotoImage(pil_disp)
        self._canvas = tk.Canvas(self._root, width=disp_w, height=disp_h, cursor="crosshair")
        self._canvas.pack(side="top")
        self._canvas.create_image(0, 0, anchor="nw", image=self._tk_img)

        btn_frame = tk.Frame(self._root)
        btn_frame.pack(side="bottom", fill="x", pady=4)
        tk.Button(btn_frame, text="✓ Done", bg="#27ae60", fg="white",
                  command=self._done).pack(side="left", padx=8)
        tk.Button(btn_frame, text="✗ Clear all", command=self._clear).pack(side="left")
        tk.Button(btn_frame, text="→ Skip (auto-caption)", command=self._skip).pack(side="right", padx=8)

        self._hint = tk.Label(self._root,
                              text="Drag to draw boxes. Click a box to label it.",
                              fg="#666")
        self._hint.pack(side="bottom")

        self._boxes: list[dict] = []
        self._rect_ids: list[int] = []
        self._start_x = self._start_y = 0
        self._cur_rect: int | None = None
        self._colour_idx = 0

        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)

    def _colour(self) -> str:
        c = _BOX_COLOURS[self._colour_idx % len(_BOX_COLOURS)]
        self._colour_idx += 1
        return c

    def _on_press(self, event) -> None:
        # Check if clicking inside an existing box (to label it)
        for i, box in enumerate(self._boxes):
            if (box["x1_px"] <= event.x <= box["x2_px"] and
                    box["y1_px"] <= event.y <= box["y2_px"]):
                self._prompt_label(i)
                return
        self._start_x, self._start_y = event.x, event.y
        c = self._colour()
        self._cur_rect = self._canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline=c, width=2
        )

    def _on_drag(self, event) -> None:
        if self._cur_rect:
            self._canvas.coords(self._cur_rect,
                                self._start_x, self._start_y,
                                event.x, event.y)

    def _on_release(self, event) -> None:
        if self._cur_rect is None:
            return
        x1, y1 = min(self._start_x, event.x), min(self._start_y, event.y)
        x2, y2 = max(self._start_x, event.x), max(self._start_y, event.y)
        if abs(x2 - x1) < 10 or abs(y2 - y1) < 10:
            self._canvas.delete(self._cur_rect)
            self._cur_rect = None
            return
        colour = self._canvas.itemcget(self._cur_rect, "outline")
        idx = len(self._boxes)
        self._rect_ids.append(self._cur_rect)
        self._cur_rect = None

        # Normalised coords
        sx, sy = 1 / self._scale, 1 / self._scale
        box = {
            "x1": round(x1 * sx / self._img_w, 4),
            "y1": round(y1 * sy / self._img_h, 4),
            "x2": round(x2 * sx / self._img_w, 4),
            "y2": round(y2 * sy / self._img_h, 4),
            "x1_px": x1, "y1_px": y1, "x2_px": x2, "y2_px": y2,
            "colour": colour,
            "label": f"region {idx + 1}",
        }
        self._boxes.append(box)
        self._draw_label(idx)
        self._prompt_label(idx)

    def _draw_label(self, idx: int) -> None:
        box = self._boxes[idx]
        self._canvas.create_text(
            box["x1_px"] + 4, box["y1_px"] + 4,
            anchor="nw", text=box["label"],
            fill=box["colour"], font=("Helvetica", 9, "bold")
        )

    def _prompt_label(self, idx: int) -> None:
        import tkinter.simpledialog as sd
        box = self._boxes[idx]
        label = sd.askstring(
            "Label region",
            f"Describe region {idx + 1}:",
            initialvalue=box.get("label", ""),
            parent=self._root,
        )
        if label:
            box["label"] = label.strip()
            self._canvas.itemconfig(self._rect_ids[idx], width=3)

    def _clear(self) -> None:
        for rid in self._rect_ids:
            self._canvas.delete(rid)
        self._canvas.delete("text_label")
        self._boxes.clear()
        self._rect_ids.clear()
        self._colour_idx = 0

    def _done(self) -> None:
        self._result = [
            {k: v for k, v in b.items() if not k.endswith("_px") and k != "colour"}
            for b in self._boxes
        ]
        self._root.destroy()

    def _skip(self) -> None:
        self._skipped = True
        self._result = []
        self._root.destroy()

    def run(self) -> tuple[list[dict], bool]:
        """Returns (annotations, skipped)."""
        self._root.mainloop()
        return (self._result or []), self._skipped


def _annotate_image(path: Path) -> tuple[list[dict], bool]:
    """Open bbox annotator; return (annotations, skipped)."""
    try:
        annotator = _BboxAnnotator(path)
        return annotator.run()
    except Exception as exc:
        rpt.warn(f"Annotation UI failed for {path.name}: {exc}. Falling back to auto-caption.")
        return [], True


# ── Qwen3-VL captioning ───────────────────────────────────────────────────────

_qwen_model = None
_qwen_processor = None


def _get_qwen(model_id: str = "Qwen/Qwen2-VL-7B-Instruct"):
    global _qwen_model, _qwen_processor
    if _qwen_model is None:
        from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
        import torch
        rpt.info(f"Loading Qwen VL model: {model_id} …")
        _qwen_model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_id,
            torch_dtype=torch.bfloat16 if __import__("torch").cuda.is_available() else torch.float32,
            device_map="auto",
        )
        _qwen_processor = AutoProcessor.from_pretrained(model_id)
    return _qwen_model, _qwen_processor


def _caption_with_qwen(
    image_path: Path,
    annotations: list[dict],
    concept_token: str | None,
    model_id: str,
) -> str:
    import torch
    from PIL import Image

    model, processor = _get_qwen(model_id)

    # Build annotation description for the prompt
    ann_lines = []
    for i, ann in enumerate(annotations, 1):
        x1, y1, x2, y2 = ann["x1"], ann["y1"], ann["x2"], ann["y2"]
        region_desc = f"top-left ({x1:.2f},{y1:.2f}) to bottom-right ({x2:.2f},{y2:.2f})"
        ann_lines.append({"label": ann["label"], "region_desc": region_desc})

    prompt_text = cap_utils.build_bfl_prompt(ann_lines, concept_token)

    image = Image.open(image_path).convert("RGB")
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
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=200,
            do_sample=False,
            temperature=None,
            top_p=None,
        )

    input_len = inputs["input_ids"].shape[1]
    generated = processor.decode(out[0][input_len:], skip_special_tokens=True)
    return cap_utils.strip_boilerplate(generated.strip())


# ── Main ──────────────────────────────────────────────────────────────────────

def run(
    dataset_dir: Path,
    concept_token: str | None = None,
    output_dir: Path | None = None,
    qwen_model_id: str = "Qwen/Qwen2-VL-7B-Instruct",
    spot_check_pct: float = 0.10,
    overwrite: bool = False,
) -> dict:
    style_mode = not concept_token
    rpt.step_header(5, "Caption — Bbox Annotation + Qwen3-VL")

    output_dir = output_dir or dataset_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    images = img_utils.iter_images(dataset_dir)
    if not images:
        rpt.warn(f"No images in {dataset_dir}")
        return {}

    if style_mode:
        rpt.info(f"Captioning {len(images)} images in style mode (no concept token).")
    else:
        rpt.info(f"Captioning {len(images)} images. Concept token: '{concept_token}'")

    captions: dict[str, str] = {}
    annotation_log: dict[str, list] = {}
    skipped_annotation: list[str] = []

    for path in images:
        txt_path = output_dir / (path.stem + ".txt")
        if txt_path.exists() and not overwrite:
            caption = txt_path.read_text(encoding="utf-8").strip()
            captions[str(path)] = caption
            rpt.info(f"Skip (exists): {path.name}")
            continue

        # Phase 5A: bbox annotation
        annotations, skipped = _annotate_image(path)
        annotation_log[str(path)] = annotations
        if skipped:
            skipped_annotation.append(str(path))

        # Phase 5B: Qwen caption
        try:
            caption = _caption_with_qwen(path, annotations, concept_token, qwen_model_id)
        except Exception as exc:
            rpt.error(f"Qwen captioning failed for {path.name}: {exc}")
            caption = concept_token or ""

        # Clean
        caption = cap_utils.strip_boilerplate(caption)

        # Token enforcement — concept mode only
        if not style_mode and concept_token:
            if not cap_utils.token_present(caption, concept_token):
                rpt.warn(f"Concept token missing in caption for {path.name} — appending.")
                caption = f"{concept_token}, {caption}"

        txt_path.write_text(caption, encoding="utf-8")
        captions[str(path)] = caption
        rpt.ok(f"{path.name} → {caption[:80]}…" if len(caption) > 80 else f"{path.name} → {caption}")

    # Token consistency check — concept mode only
    missing_token: list[str] = []
    if not style_mode and concept_token:
        missing_token = cap_utils.verify_token_consistency(captions, concept_token)
        if missing_token:
            rpt.warn(f"Token '{concept_token}' missing in {len(missing_token)} captions:")
            for p in missing_token:
                rpt.warn(f"  {Path(p).name}")

    # Caption length outliers
    short = [p for p, c in captions.items() if not cap_utils.caption_length_ok(c, min_chars=10)]
    long_ = [p for p, c in captions.items() if not cap_utils.caption_length_ok(c, max_chars=600)]
    if short:
        rpt.warn(f"{len(short)} captions suspiciously short (< 10 chars)")
    if long_:
        rpt.warn(f"{len(long_)} captions very long (> 600 chars)")

    # Spot-check
    if captions:
        n_check = max(1, int(len(captions) * spot_check_pct))
        sample = random.sample(list(captions.items()), min(n_check, len(captions)))
        from rich.table import Table
        from rich import box
        from ..utils.report import console
        t = Table(title=f"Spot-check ({n_check} / {len(captions)})", box=box.SIMPLE_HEAVY)
        t.add_column("File", style="cyan", max_width=35)
        t.add_column("Caption", style="white")
        for p, c in sample:
            t.add_row(Path(p).name, c[:120] + ("…" if len(c) > 120 else ""))
        console.print(t)

    report = {
        "total": len(images),
        "captioned": len(captions),
        "skipped_annotation": skipped_annotation,
        "missing_token": missing_token,
        "short_captions": short,
        "long_captions": long_,
        "spot_check_sample": [p for p, _ in sample] if captions else [],
    }
    rpt.save_report(report, output_dir / "step5_report.json")
    return report
