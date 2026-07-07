from __future__ import annotations

from pathlib import Path


from prepare_lora_kit.steps.quality_gate.gallery.constants import _THUMB, _COLS, _PASS, _FAIL, _quality_color
from prepare_lora_kit.steps.quality_gate.gallery.tooltip import HoverPreview

def _gallery_review(items: list[tuple[Path, dict]]) -> dict[str, str]:
    """
    Show every image in a scrollable grid.

    Border: green = keep, red = reject (seeded from auto_reject).
    Left-click toggles keep/reject. Hover shows per-gate scores + overall quality.
    Returns {path_str: "keep"|"reject"}.
    """
    import tkinter as tk
    from PIL import Image as PILImage, ImageTk

    decisions: dict[str, str] = {
        str(p): ("reject" if info["auto_reject"] else "keep") for p, info in items
    }

    root = tk.Tk()
    root.title("Step 1 — Source Review")
    root.configure(bg="#1e1e1e")

    header = tk.Label(root, bg="#1e1e1e", fg="#dddddd", font=("TkDefaultFont", 11, "bold"))
    header.pack(side="top", fill="x", padx=8, pady=6)

    # scrollable canvas + inner frame
    canvas = tk.Canvas(root, bg="#1e1e1e", highlightthickness=0)
    vbar = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vbar.set)
    vbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    grid = tk.Frame(canvas, bg="#1e1e1e")
    canvas.create_window((0, 0), window=grid, anchor="nw")
    grid.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
    canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
    canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

    # hover preview popup: full-size image + scores (browser-style)
    preview = HoverPreview(root)

    refs: list = []  # keep thumbnail PhotoImage refs alive

    def _update_header():
        kept = sum(1 for d in decisions.values() if d == "keep")
        header.config(text=f"{len(items)} images   •   keep {kept}   •   "
                           f"reject {len(items) - kept}   •   click to toggle")

    cells: dict[str, tk.Frame] = {}

    def _paint(key: str):
        cells[key].config(highlightbackground=_PASS if decisions[key] == "keep" else _FAIL,
                          highlightcolor=_PASS if decisions[key] == "keep" else _FAIL)

    def _toggle(key: str):
        decisions[key] = "reject" if decisions[key] == "keep" else "keep"
        _paint(key)
        _update_header()

    for idx, (path, info) in enumerate(items):
        key = str(path)
        cell = tk.Frame(grid, bg="#1e1e1e", highlightthickness=4, bd=0)
        cell.grid(row=idx // _COLS, column=idx % _COLS, padx=6, pady=6)

        cells[key] = cell
        try:
            im = PILImage.open(path).convert("RGB")
            im.thumbnail((_THUMB, _THUMB))
            photo = ImageTk.PhotoImage(im)
            refs.append(photo)
            thumb = tk.Label(cell, image=photo, bg="#1e1e1e")
        except Exception:
            thumb = tk.Label(cell, text="(no preview)", width=24, height=10,
                             bg="#333333", fg="#aaaaaa")
        thumb.pack()

        caption = tk.Label(cell, text=f"{info['quality']}/100",
                           bg="#1e1e1e", fg=_quality_color(info["quality"]),
                           font=("TkDefaultFont", 9, "bold"))
        caption.pack()
        name = tk.Label(cell, text=path.name, bg="#1e1e1e", fg="#999999",
                        font=("TkDefaultFont", 8), wraplength=_THUMB)
        name.pack()

        for w in (cell, thumb, caption, name):
            w.bind("<Button-1>", lambda e, k=key: _toggle(k))
            w.bind("<Enter>", lambda e, p=path, i=info: preview.schedule(e, p, i))
            w.bind("<Leave>", preview.hide)
        _paint(key)

    _update_header()

    btn_bar = tk.Frame(root, bg="#1e1e1e")
    btn_bar.pack(side="bottom", fill="x")
    tk.Button(btn_bar, text="Done", command=root.destroy,
              bg="#2e7d32", fg="white", font=("TkDefaultFont", 10, "bold")).pack(
        side="right", padx=8, pady=6)

    root.geometry("1100x800")
    root.mainloop()
    return decisions
