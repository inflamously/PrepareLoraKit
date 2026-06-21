from __future__ import annotations
from pathlib import Path

from ...utils import report as rpt

_BOX_COLOURS = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c"]


# ── Bbox annotation UI (tkinter) ──────────────────────────────────────────────

class _BboxAnnotator:
    """
    Opens a tkinter window for the given image.
    User draws bounding boxes by click-drag; clicks on a completed box to add a label.
    Returns list of {x1,y1,x2,y2,label} in normalised [0,1] coords.
    """

    def __init__(self, image_path: Path, captioner=None, max_w: int = 1100, max_h: int = 750):
        import tkinter as tk
        from PIL import Image, ImageTk

        self._path = image_path
        self._captioner = captioner
        self._result: list[dict] | None = None
        self._skipped = False
        self._skip_all_flag = False

        pil = Image.open(image_path).convert("RGB")
        self._pil = pil  # full-res original, used to crop regions for Box Caption
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
        tk.Button(btn_frame, text="✓ Done", bg="#27ae60", fg="white", command=self._done).pack(side="right", padx=8)
        tk.Button(btn_frame, text="✗ Clear Boxes", command=self._clear).pack(side="right")
        tk.Button(btn_frame, text="→ Skip All", command=self._skip_all).pack(side="left", padx=8)
        tk.Button(btn_frame, text="→ Skip", command=self._skip).pack(side="left")
        tk.Button(btn_frame, text="🅒 Box Caption", bg="#2980b9", fg="white",
                  command=self._box_caption).pack(side="left", expand=True)

        self._hint = tk.Label(self._root,
                              text="Drag to draw + label. Shift-drag = empty box for VL. "
                                   "Ctrl+drag draws over a box. Right-click deletes. "
                                   "'Box Caption' fills empty boxes.",
                              fg="#666")
        self._hint.pack(side="bottom")

        self._boxes: list[dict] = []
        self._start_x = self._start_y = 0
        self._cur_rect: int | None = None
        self._colour_idx = 0
        self._draw_empty = False
        self._selected_idx: int | None = None

        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._canvas.bind("<ButtonPress-3>", self._on_delete)

    def _colour(self) -> str:
        c = _BOX_COLOURS[self._colour_idx % len(_BOX_COLOURS)]
        self._colour_idx += 1
        return c

    def _box_at(self, x: int, y: int) -> int | None:
        """Index of the smallest box containing the point (foreground), else None."""
        best, best_area = None, None
        for i, b in enumerate(self._boxes):
            if b["x1_px"] <= x <= b["x2_px"] and b["y1_px"] <= y <= b["y2_px"]:
                if best_area is None or b["area"] < best_area:
                    best, best_area = i, b["area"]
        return best

    def _restack(self) -> None:
        """Largest box in back, smallest in front, so small boxes stay clickable."""
        for b in sorted(self._boxes, key=lambda b: b["area"], reverse=True):
            self._canvas.tag_raise(b["rect_id"])
            if b.get("label_id"):
                self._canvas.tag_raise(b["label_id"])

    def _on_press(self, event) -> None:
        # Plain click inside a box labels it. Ctrl- or Shift-drag forces a new box
        # on top; Shift additionally marks it empty (no label prompt — VL fills it).
        ctrl = bool(event.state & 0x0004)
        shift = bool(event.state & 0x0001)
        self._draw_empty = shift
        if not ctrl and not shift:
            hit = self._box_at(event.x, event.y)
            if hit is not None:
                self._selected_idx = hit
                self._prompt_label(hit)
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
        rect_id = self._cur_rect
        self._cur_rect = None
        empty = self._draw_empty
        self._draw_empty = False

        # Normalised coords
        sx, sy = 1 / self._scale, 1 / self._scale
        box = {
            "x1": round(x1 * sx / self._img_w, 4),
            "y1": round(y1 * sy / self._img_h, 4),
            "x2": round(x2 * sx / self._img_w, 4),
            "y2": round(y2 * sy / self._img_h, 4),
            "x1_px": x1, "y1_px": y1, "x2_px": x2, "y2_px": y2,
            "area": (x2 - x1) * (y2 - y1),
            "colour": colour,
            "label": "" if empty else f"region {idx + 1}",
            "empty": empty,
            "rect_id": rect_id,
            "label_id": None,
        }
        self._boxes.append(box)
        self._selected_idx = idx
        self._draw_label(idx)
        self._restack()
        if not empty:
            self._prompt_label(idx)

    def _draw_label(self, idx: int) -> None:
        box = self._boxes[idx]
        box["label_id"] = self._canvas.create_text(
            box["x1_px"] + 4, box["y1_px"] + 4,
            anchor="nw", text=box["label"] or "(empty)",
            fill=box["colour"], font=("Helvetica", 9, "bold")
        )

    def _prompt_label(self, idx: int) -> None:
        box = self._boxes[idx]
        text = self._edit_text(f"Describe region {idx + 1}", box.get("label", ""))
        if text and text.strip():
            box["label"] = " ".join(text.split())  # flatten newlines → single-line label
            box["empty"] = False
            self._canvas.itemconfig(box["rect_id"], width=3)
            if box.get("label_id"):
                self._canvas.itemconfig(box["label_id"], text=box["label"])

    def _edit_text(self, title: str, initial: str) -> str | None:
        """Modal multi-line editor. Returns the text, or None if cancelled."""
        import tkinter as tk
        win = tk.Toplevel(self._root)
        win.title(title)
        win.transient(self._root)

        tk.Label(win, text=title, anchor="w").pack(fill="x", padx=8, pady=(8, 2))
        txt = tk.Text(win, width=60, height=8, wrap="word", font=("Helvetica", 11))
        txt.pack(padx=8, pady=4, fill="both", expand=True)
        txt.insert("1.0", initial or "")
        txt.focus_set()

        result: dict[str, str | None] = {"value": None}

        def ok(event=None):
            result["value"] = txt.get("1.0", "end-1c")
            win.destroy()

        def cancel(event=None):
            result["value"] = None
            win.destroy()

        btns = tk.Frame(win)
        btns.pack(fill="x", padx=8, pady=(2, 8))
        tk.Button(btns, text="OK  (Ctrl+Enter)", bg="#27ae60", fg="white",
                  command=ok).pack(side="right", padx=4)
        tk.Button(btns, text="Cancel  (Esc)", command=cancel).pack(side="right")

        win.bind("<Control-Return>", ok)
        win.bind("<Escape>", cancel)
        win.update_idletasks()
        win.grab_set()
        self._root.wait_window(win)
        return result["value"]

    def _on_delete(self, event) -> None:
        i = self._box_at(event.x, event.y)
        if i is None:
            return
        box = self._boxes.pop(i)
        self._selected_idx = None
        self._canvas.delete(box["rect_id"])
        if box.get("label_id"):
            self._canvas.delete(box["label_id"])

    def _clear(self) -> None:
        for box in self._boxes:
            self._canvas.delete(box["rect_id"])
            if box.get("label_id"):
                self._canvas.delete(box["label_id"])
        if self._cur_rect is not None:
            self._canvas.delete(self._cur_rect)
            self._cur_rect = None
        self._boxes.clear()
        self._colour_idx = 0
        self._selected_idx = None

    def _set_hint(self, text: str) -> None:
        self._hint.config(text=text)
        self._root.update_idletasks()

    def _crop_for(self, box: dict):
        """Crop the original full-res image to the box region."""
        l = int(box["x1"] * self._img_w)
        t = int(box["y1"] * self._img_h)
        r = int(box["x2"] * self._img_w)
        b = int(box["y2"] * self._img_h)
        return self._pil.crop((l, t, max(l + 1, r), max(t + 1, b)))

    def _box_caption(self) -> None:
        """Run the VL captioner on the selected box, or all empty boxes."""
        if self._captioner is None:
            self._set_hint("No VL captioner available in this run.")
            return
        if self._selected_idx is not None and self._selected_idx < len(self._boxes):
            targets = [self._boxes[self._selected_idx]]
        else:
            targets = [b for b in self._boxes if b.get("empty")]
        if not targets:
            self._set_hint("Select a box, or Shift-drag to add an empty box, then Box Caption.")
            return
        total = len(targets)
        for n, box in enumerate(targets, 1):
            self._set_hint(f"Captioning region {n}/{total} …")
            try:
                result = self._captioner(self._crop_for(box), {"source_path": str(self._path), "box": box})
            except Exception as exc:
                rpt.warn(f"Box caption failed: {exc}")
                result = {}
            if isinstance(result, dict):
                text = str(result.get("caption") or "").strip()
                if result.get("crop_path"):
                    box["crop_path"] = result["crop_path"]
                if result.get("crop_name"):
                    box["crop_name"] = result["crop_name"]
            else:
                text = str(result or "").strip()
            if text:
                box["label"] = text
                box["empty"] = False
                self._canvas.itemconfig(box["rect_id"], width=3)
                self._canvas.itemconfig(box["label_id"], text=text)
        self._set_hint(f"Captioned {total} region(s). Click a box to edit.")

    def _done(self) -> None:
        drop = {"colour", "rect_id", "label_id", "empty", "area"}
        self._result = [
            {k: v for k, v in b.items() if not k.endswith("_px") and k not in drop}
            for b in self._boxes if b["label"].strip()
        ]
        self._root.destroy()

    def _skip(self) -> None:
        self._skipped = True
        self._result = []
        self._root.destroy()

    def _skip_all(self) -> None:
        self._skipped = True
        self._skip_all_flag = True
        self._result = []
        self._root.destroy()

    def run(self) -> tuple[list[dict], bool, bool]:
        """Returns (annotations, skipped, skip_all)."""
        self._root.mainloop()
        return (self._result or []), self._skipped, self._skip_all_flag


def _annotate_image(path: Path, captioner=None) -> tuple[list[dict], bool, bool]:
    """Open bbox annotator; return (annotations, skipped, skip_all)."""
    try:
        annotator = _BboxAnnotator(path, captioner=captioner)
        return annotator.run()
    except Exception as exc:
        rpt.warn(f"Annotation UI failed for {path.name}: {exc}. Falling back to auto-caption.")
        return [], True, False
