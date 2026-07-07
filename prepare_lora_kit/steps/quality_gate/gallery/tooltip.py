from __future__ import annotations

from pathlib import Path


from prepare_lora_kit.steps.quality_gate.gallery.constants import _PREVIEW, HOVER_TIMEOUT

class HoverPreview:
    """
    Browser-style hover popup: a full-size preview image plus per-gate scores.

    Encapsulates the floating Toplevel, its image/label widgets, the preview
    PhotoImage cache, and the pending `after` callback id (so concurrent
    galleries no longer share a module-level timer handle).
    """

    def __init__(self, root):
        import tkinter as tk

        self._root = root

        tip = tk.Toplevel(root)
        tip.withdraw()
        tip.overrideredirect(True)
        tip.configure(bg="#000000", bd=1, relief="solid")
        self._tip = tip

        self._img = tk.Label(tip, bg="#000000")
        self._img.pack()
        self._lbl = tk.Label(tip, justify="left", bg="#000000", fg="#eeeeee",
                             font=("TkFixedFont", 9), padx=6, pady=4)
        self._lbl.pack(fill="x")

        self._cache: dict[str, "object"] = {}  # path → ImageTk.PhotoImage | None
        self._after_id = None

    def _photo(self, path: Path):
        from PIL import Image as PILImage, ImageTk

        key = str(path)
        if key not in self._cache:
            try:
                im = PILImage.open(path).convert("RGB")
                im.thumbnail((_PREVIEW, _PREVIEW))
                self._cache[key] = ImageTk.PhotoImage(im)
            except Exception:
                self._cache[key] = None
        return self._cache[key]

    @staticmethod
    def _text(info: dict) -> str:
        lines = [f"quality: {info['quality']}/100"]
        for k, v in info["scores"].items():
            lines.append(f"  {k:<12}: {v if v is not None else 'n/a'}")
        if info["auto_reasons"]:
            lines.append("flags: " + ", ".join(info["auto_reasons"]))
        return "\n".join(lines)

    def _place(self, event):
        # clamp inside screen so the large preview never spills off-edge
        self._tip.update_idletasks()
        w, h = self._tip.winfo_width(), self._tip.winfo_height()
        sw, sh = self._root.winfo_screenwidth(), self._root.winfo_screenheight()
        x = event.x_root + 20
        y = event.y_root + 12
        if x + w > sw:
            x = event.x_root - w - 20
        if y + h > sh:
            y = max(0, sh - h)
        self._tip.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _show(self, event, path, info):
        photo = self._photo(path)
        if photo is not None:
            self._img.config(image=photo)
            self._img.image = photo

        self._lbl.config(text=self._text(info))
        self._tip.deiconify()
        self._place(event)

    def schedule(self, event, path, info):
        """Arm the popup to appear after the hover delay."""
        self.cancel()
        self._after_id = self._root.after(
            HOVER_TIMEOUT, lambda: self._show(event, path, info)
        )

    def cancel(self):
        """Drop any pending (not-yet-shown) popup."""
        if self._after_id is not None:
            self._root.after_cancel(self._after_id)
            self._after_id = None

    def hide(self, _event=None):
        """Cancel a pending popup and hide the visible one."""
        self.cancel()
        self._tip.withdraw()
