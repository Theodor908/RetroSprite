"""Text tool dialog for RetroSprite — Aseprite-style modal text entry."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog

from src.ui.theme import (
    ACCENT_CYAN, BG_DEEP, BG_PANEL, BG_PANEL_ALT,
    BUTTON_BG, BUTTON_HOVER, TEXT_PRIMARY, TEXT_SECONDARY,
)


class TextDialog(tk.Toplevel):
    """Modal dialog for entering text with font/size/spacing/align controls.

    While the dialog is open, calls `on_preview(text, settings)` on every
    change so the caller can render a live preview on the canvas.
    """

    def __init__(self, parent, loaded_fonts: dict, on_preview=None,
                 initial_settings: dict | None = None):
        super().__init__(parent)
        self.title("Text Tool")
        self.configure(bg=BG_DEEP)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result: dict | None = None  # Set on OK
        self._on_preview = on_preview
        self._loaded_fonts = loaded_fonts

        s = initial_settings or {}
        font = ("Consolas", 9)

        # --- Text input ---
        tk.Label(self, text="Text:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font).pack(anchor="w", padx=10, pady=(10, 2))
        self._text_input = tk.Text(self, width=30, height=5,
                                    bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                                    font=font, insertbackground=ACCENT_CYAN,
                                    relief="flat", wrap="word",
                                    highlightthickness=1,
                                    highlightbackground=ACCENT_CYAN)
        self._text_input.pack(padx=10, pady=(0, 6), fill="x")
        self._text_input.bind("<KeyRelease>", lambda e: self._on_change())

        # --- Font row ---
        font_row = tk.Frame(self, bg=BG_DEEP)
        font_row.pack(fill="x", padx=10, pady=2)

        tk.Label(font_row, text="Font:", bg=BG_DEEP, fg=TEXT_SECONDARY,
                 font=("Consolas", 8)).pack(side="left")
        font_choices = ["Tiny 3x5", "Standard 5x7"]
        for name in loaded_fonts:
            font_choices.append(name)
        font_choices.append("Load Font...")
        self._font_var = tk.StringVar(value=s.get("font_name", "Standard 5x7"))
        font_menu = tk.OptionMenu(font_row, self._font_var, *font_choices,
                                   command=self._on_font_change)
        font_menu.config(bg=BUTTON_BG, fg=TEXT_PRIMARY, font=("Consolas", 8),
                         highlightthickness=0, relief="flat",
                         activebackground=BUTTON_HOVER)
        font_menu.pack(side="left", padx=4)

        tk.Label(font_row, text="Size:", bg=BG_DEEP, fg=TEXT_SECONDARY,
                 font=("Consolas", 8)).pack(side="left", padx=(8, 0))
        self._size_var = tk.IntVar(value=s.get("font_size", 12))
        self._size_spin = tk.Spinbox(font_row, from_=4, to=128, width=3,
                                      textvariable=self._size_var,
                                      font=("Consolas", 8),
                                      bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                                      buttonbackground=BUTTON_BG,
                                      command=self._on_change)
        self._size_spin.pack(side="left", padx=4)
        is_ttf = self._font_var.get() not in ("Tiny 3x5", "Standard 5x7")
        self._size_spin.config(state="normal" if is_ttf else "disabled")

        # --- Spacing row ---
        opts_row = tk.Frame(self, bg=BG_DEEP)
        opts_row.pack(fill="x", padx=10, pady=2)

        tk.Label(opts_row, text="Letter Spacing:", bg=BG_DEEP, fg=TEXT_SECONDARY,
                 font=("Consolas", 8)).pack(side="left")
        self._spacing_var = tk.IntVar(value=s.get("spacing", 1))
        tk.Spinbox(opts_row, from_=0, to=10, width=2,
                   textvariable=self._spacing_var,
                   font=("Consolas", 8),
                   bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                   buttonbackground=BUTTON_BG,
                   command=self._on_change).pack(side="left", padx=4)
        tk.Label(opts_row, text="px", bg=BG_DEEP, fg=TEXT_SECONDARY,
                 font=("Consolas", 8)).pack(side="left")

        # --- Buttons ---
        btn_row = tk.Frame(self, bg=BG_DEEP)
        btn_row.pack(fill="x", pady=(8, 10), padx=10)
        tk.Button(btn_row, text="Cancel", bg=BUTTON_BG, fg=TEXT_PRIMARY,
                  font=font, relief="flat", padx=12,
                  command=self._on_cancel).pack(side="right", padx=4)
        tk.Button(btn_row, text="OK", bg=ACCENT_CYAN, fg=BG_DEEP,
                  font=("Consolas", 9, "bold"), relief="flat", padx=12,
                  command=self._on_ok).pack(side="right", padx=4)

        # Focus the text input
        self._text_input.focus_set()

        # Center on parent
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def get_settings(self) -> dict:
        """Return current dialog settings."""
        return {
            "text": self._text_input.get("1.0", "end-1c"),
            "font_name": self._font_var.get(),
            "font_size": self._size_var.get(),
            "spacing": self._spacing_var.get(),
            "line_height": 2,
            "align": "left",
        }

    def _on_change(self):
        """Called on any text or setting change — trigger preview."""
        if self._on_preview:
            self._on_preview(self.get_settings())

    def _on_font_change(self, value):
        """Handle font dropdown change."""
        if value == "Load Font...":
            path = filedialog.askopenfilename(
                title="Load Font",
                filetypes=[("Font files", "*.ttf *.otf"), ("All files", "*.*")],
            )
            if path:
                name = os.path.splitext(os.path.basename(path))[0]
                self._loaded_fonts[name] = path
                self._font_var.set(name)
                # Rebuild would be complex — just enable size
                self._size_spin.config(state="normal")
            else:
                self._font_var.set("Standard 5x7")
                self._size_spin.config(state="disabled")
                return

        is_ttf = value not in ("Tiny 3x5", "Standard 5x7")
        self._size_spin.config(state="normal" if is_ttf else "disabled")
        self._on_change()

    def _on_ok(self):
        self.result = self.get_settings()
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()
