"""Tag add/edit dialog for RetroSprite."""
from __future__ import annotations
import tkinter as tk
from src.ui.theme import (
    ACCENT_CYAN, BG_DEEP, BG_PANEL, BG_PANEL_ALT,
    BUTTON_BG, BUTTON_HOVER, TEXT_PRIMARY, TEXT_SECONDARY,
)


class TagDialog(tk.Toplevel):
    """Modal dialog for creating or editing a frame tag."""

    def __init__(self, parent, frame_count: int, tag: dict | None = None):
        super().__init__(parent)
        self.title("Edit Tag" if tag else "Add Tag")
        self.configure(bg=BG_DEEP)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result: dict | None = None

        font = ("Consolas", 9)
        t = tag or {}

        # Name
        row = tk.Frame(self, bg=BG_DEEP)
        row.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(row, text="Name:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font, width=8, anchor="w").pack(side="left")
        self._name_var = tk.StringVar(value=t.get("name", ""))
        tk.Entry(row, textvariable=self._name_var, font=font,
                 bg=BG_PANEL_ALT, fg=TEXT_PRIMARY, insertbackground=ACCENT_CYAN,
                 width=20).pack(side="left", fill="x", expand=True)

        # Color
        row2 = tk.Frame(self, bg=BG_DEEP)
        row2.pack(fill="x", padx=10, pady=4)
        tk.Label(row2, text="Color:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font, width=8, anchor="w").pack(side="left")
        self._color = t.get("color", "#00ff00")
        self._color_swatch = tk.Canvas(row2, width=40, height=18,
                                        highlightthickness=1,
                                        highlightbackground=TEXT_SECONDARY,
                                        cursor="hand2")
        self._color_swatch.pack(side="left", padx=(0, 8))
        self._color_swatch.configure(bg=self._color)
        self._color_swatch.bind("<Button-1>", lambda e: self._pick_color())
        # Quick color buttons
        for c in ["#00ff00", "#ff6600", "#ff00ff", "#00bfff", "#ffff00", "#ff4444"]:
            btn = tk.Button(row2, bg=c, width=2, relief="flat",
                            command=lambda col=c: self._set_color(col))
            btn.pack(side="left", padx=1)

        # Start / End frames
        row3 = tk.Frame(self, bg=BG_DEEP)
        row3.pack(fill="x", padx=10, pady=4)
        tk.Label(row3, text="Start:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font, width=8, anchor="w").pack(side="left")
        self._start_var = tk.IntVar(value=t.get("start", 0) + 1)
        tk.Spinbox(row3, from_=1, to=frame_count, width=4,
                   textvariable=self._start_var, font=font,
                   bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                   buttonbackground=BUTTON_BG).pack(side="left", padx=(0, 12))
        tk.Label(row3, text="End:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font, anchor="w").pack(side="left")
        self._end_var = tk.IntVar(value=t.get("end", 0) + 1)
        tk.Spinbox(row3, from_=1, to=frame_count, width=4,
                   textvariable=self._end_var, font=font,
                   bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                   buttonbackground=BUTTON_BG).pack(side="left")

        # Buttons
        btn_row = tk.Frame(self, bg=BG_DEEP)
        btn_row.pack(fill="x", padx=10, pady=(8, 10))
        tk.Button(btn_row, text="Cancel", bg=BUTTON_BG, fg=TEXT_PRIMARY,
                  font=font, relief="flat", padx=12,
                  command=self.destroy).pack(side="right", padx=4)
        tk.Button(btn_row, text="OK", bg=ACCENT_CYAN, fg=BG_DEEP,
                  font=("Consolas", 9, "bold"), relief="flat", padx=12,
                  command=self._on_ok).pack(side="right", padx=4)

        # Center
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _pick_color(self):
        from tkinter import colorchooser
        color = colorchooser.askcolor(initialcolor=self._color, parent=self)
        if color[1]:
            self._set_color(color[1])

    def _set_color(self, color):
        self._color = color
        self._color_swatch.configure(bg=color)

    def _on_ok(self):
        name = self._name_var.get().strip()
        if not name:
            return
        start = self._start_var.get() - 1  # to 0-based
        end = self._end_var.get() - 1
        if end < start:
            end = start
        self.result = {
            "name": name,
            "color": self._color,
            "start": start,
            "end": end,
        }
        self.destroy()
