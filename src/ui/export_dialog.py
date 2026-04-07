"""Unified export dialog for RetroSprite."""
from __future__ import annotations
import tkinter as tk
from tkinter import filedialog
from dataclasses import dataclass
from src.ui.theme import (
    BG_DEEP, BG_PANEL, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, ACCENT_MAGENTA, BUTTON_BG, BUTTON_HOVER,
)


@dataclass
class ExportSettings:
    """Settings returned by ExportDialog."""
    format: str       # "png", "gif", "webp", "apng", "sheet", "frames"
    scale: int        # 1-16
    frame: int        # frame index (for png single)
    layer: str | None  # layer name or None for flattened
    columns: int      # sheet columns (0=auto)
    output_path: str  # file path from save dialog
    tag_start: int | None = None   # start frame for tag export
    tag_end: int | None = None     # end frame for tag export


# File extension filters per format
_FORMAT_FILTERS = {
    "png": [("PNG files", "*.png")],
    "gif": [("GIF files", "*.gif")],
    "webp": [("WebP files", "*.webp")],
    "apng": [("APNG files", "*.apng *.png")],
    "sheet": [("PNG files", "*.png")],
    "frames": [("PNG files", "*.png")],
}

# Default extensions per format
_FORMAT_EXT = {
    "png": ".png",
    "gif": ".gif",
    "webp": ".webp",
    "apng": ".apng",
    "sheet": ".png",
    "frames": ".png",
}

# Formats that support per-frame options
_SINGLE_FRAME_FORMATS = {"png"}
# Formats that support layer selection
_LAYER_FORMATS = {"png", "frames"}
# Formats that support columns option
_COLUMN_FORMATS = {"sheet"}
# Formats that support tag range filtering (multi-frame exports)
_TAG_FORMATS = {"gif", "webp", "apng", "sheet", "frames"}


class ExportDialog(tk.Toplevel):
    """Unified export dialog for all RetroSprite export formats.

    Usage:
        dialog = ExportDialog(parent, timeline, palette, last_settings)
        parent.wait_window(dialog)
        settings = dialog.result  # ExportSettings or None
    """

    def __init__(self, parent, timeline, palette, last_settings=None):
        super().__init__(parent)
        self.title("Export...")
        self.configure(bg=BG_DEEP)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._timeline = timeline
        self._palette = palette
        self._last = last_settings or {}
        self.result: ExportSettings | None = None

        self._build_ui()
        self._on_format_change()
        self._update_preview()

        # Center on parent
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}
        font = ("Consolas", 9)

        # --- Format ---
        row = tk.Frame(self, bg=BG_DEEP)
        row.pack(fill="x", **pad)
        tk.Label(row, text="Format:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font, width=10, anchor="w").pack(side="left")
        self._fmt_var = tk.StringVar(value=self._last.get("format", "png"))
        formats = ["png", "gif", "webp", "apng", "sheet", "frames"]
        self._fmt_menu = tk.OptionMenu(row, self._fmt_var, *formats,
                                        command=lambda _: self._on_format_change())
        self._fmt_menu.config(bg=BUTTON_BG, fg=TEXT_PRIMARY, font=font,
                              activebackground=BUTTON_HOVER,
                              highlightthickness=0)
        self._fmt_menu.pack(side="left", fill="x", expand=True)

        # --- Tag filter (shown only for multi-frame formats) ---
        tag_row = tk.Frame(self, bg=BG_DEEP)
        tk.Label(tag_row, text="Tag:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font, width=10, anchor="w").pack(side="left")
        tag_choices = ["All Frames"]
        for tag in self._timeline.tags:
            tag_choices.append(f"{tag['name']} ({tag['start']+1}-{tag['end']+1})")
        self._tag_var = tk.StringVar(value="All Frames")
        self._tag_menu = tk.OptionMenu(tag_row, self._tag_var, *tag_choices)
        self._tag_menu.config(bg=BUTTON_BG, fg=TEXT_PRIMARY, font=font,
                              activebackground=BUTTON_HOVER,
                              highlightthickness=0)
        self._tag_menu.pack(side="left", fill="x", expand=True)
        self._tag_row = tag_row

        # --- Scale ---
        scale_row = tk.Frame(self, bg=BG_DEEP)
        scale_row.pack(fill="x", **pad)
        tk.Label(scale_row, text="Scale:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font, width=10, anchor="w").pack(side="left")
        self._scale_var = tk.IntVar(value=self._last.get("scale", 1))
        for s in [1, 2, 4, 8]:
            tk.Radiobutton(
                scale_row, text=f"{s}x", variable=self._scale_var, value=s,
                bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
                activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
                font=font, command=self._update_preview
            ).pack(side="left", padx=2)
        tk.Label(scale_row, text="Custom:", bg=BG_DEEP, fg=TEXT_SECONDARY,
                 font=font).pack(side="left", padx=(8, 2))
        self._custom_scale = tk.Spinbox(
            scale_row, from_=1, to=16, width=3, font=font,
            bg=BG_PANEL, fg=TEXT_PRIMARY, buttonbackground=BUTTON_BG,
            command=self._on_custom_scale
        )
        self._custom_scale.pack(side="left")
        self._custom_scale.bind("<Return>", lambda e: self._on_custom_scale())

        # --- Frame selector ---
        self._frame_row = tk.Frame(self, bg=BG_DEEP)
        self._frame_row.pack(fill="x", **pad)
        tk.Label(self._frame_row, text="Frame:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font, width=10, anchor="w").pack(side="left")
        self._frame_var = tk.StringVar(value="current")
        tk.Radiobutton(
            self._frame_row, text="Current frame", variable=self._frame_var,
            value="current", bg=BG_DEEP, fg=TEXT_PRIMARY,
            selectcolor=BG_PANEL, font=font
        ).pack(side="left")
        tk.Radiobutton(
            self._frame_row, text="All frames", variable=self._frame_var,
            value="all", bg=BG_DEEP, fg=TEXT_PRIMARY,
            selectcolor=BG_PANEL, font=font
        ).pack(side="left")

        # --- Layer selector ---
        self._layer_row = tk.Frame(self, bg=BG_DEEP)
        self._layer_row.pack(fill="x", **pad)
        tk.Label(self._layer_row, text="Layer:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font, width=10, anchor="w").pack(side="left")
        layer_names = ["All (flattened)"]
        frame_obj = self._timeline.get_frame_obj(self._timeline.current_index)
        layer_names += [l.name for l in frame_obj.layers]
        self._layer_var = tk.StringVar(value="All (flattened)")
        self._layer_menu = tk.OptionMenu(self._layer_row, self._layer_var,
                                          *layer_names)
        self._layer_menu.config(bg=BUTTON_BG, fg=TEXT_PRIMARY, font=font,
                                activebackground=BUTTON_HOVER,
                                highlightthickness=0)
        self._layer_menu.pack(side="left", fill="x", expand=True)

        # --- Sheet columns ---
        self._col_row = tk.Frame(self, bg=BG_DEEP)
        self._col_row.pack(fill="x", **pad)
        tk.Label(self._col_row, text="Columns:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font, width=10, anchor="w").pack(side="left")
        self._col_var = tk.IntVar(value=0)
        self._col_spin = tk.Spinbox(
            self._col_row, from_=0, to=100, width=4, font=font,
            textvariable=self._col_var,
            bg=BG_PANEL, fg=TEXT_PRIMARY, buttonbackground=BUTTON_BG,
        )
        self._col_spin.pack(side="left")
        tk.Label(self._col_row, text="(0 = auto)", bg=BG_DEEP,
                 fg=TEXT_SECONDARY, font=font).pack(side="left", padx=4)

        # --- Output size preview ---
        self._preview_label = tk.Label(
            self, text="Output: --", bg=BG_DEEP, fg=ACCENT_CYAN,
            font=("Consolas", 9, "bold")
        )
        self._preview_label.pack(fill="x", **pad)

        # --- Buttons ---
        btn_row = tk.Frame(self, bg=BG_DEEP)
        btn_row.pack(fill="x", padx=8, pady=8)
        tk.Button(
            btn_row, text="Export", command=self._on_export,
            bg=ACCENT_CYAN, fg=BG_DEEP, font=("Consolas", 9, "bold"),
            activebackground=ACCENT_MAGENTA, width=10
        ).pack(side="right", padx=4)
        tk.Button(
            btn_row, text="Cancel", command=self._on_cancel,
            bg=BUTTON_BG, fg=TEXT_PRIMARY, font=font,
            activebackground=BUTTON_HOVER, width=10
        ).pack(side="right", padx=4)

    def _on_format_change(self):
        fmt = self._fmt_var.get()
        # Hide all optional rows first
        self._tag_row.pack_forget()
        self._frame_row.pack_forget()
        self._layer_row.pack_forget()
        self._col_row.pack_forget()
        # Re-pack in correct order, before the preview label
        if fmt in _TAG_FORMATS:
            self._tag_row.pack(fill="x", padx=8, pady=4,
                               before=self._preview_label)
        if fmt in _SINGLE_FRAME_FORMATS:
            self._frame_row.pack(fill="x", padx=8, pady=4,
                                 before=self._preview_label)
        if fmt in _LAYER_FORMATS:
            self._layer_row.pack(fill="x", padx=8, pady=4,
                                 before=self._preview_label)
        if fmt in _COLUMN_FORMATS:
            self._col_row.pack(fill="x", padx=8, pady=4,
                               before=self._preview_label)
        self._update_preview()

    def _on_custom_scale(self):
        try:
            val = int(self._custom_scale.get())
            if 1 <= val <= 16:
                self._scale_var.set(val)
                self._update_preview()
        except ValueError:
            pass

    def _update_preview(self):
        s = self._scale_var.get()
        w = self._timeline.width * s
        h = self._timeline.height * s
        fmt = self._fmt_var.get()
        if fmt == "sheet":
            fc = self._timeline.frame_count
            cols = self._col_var.get() or fc
            rows = (fc + cols - 1) // cols
            w = self._timeline.width * s * cols
            h = self._timeline.height * s * rows
        self._preview_label.config(text=f"Output: {w}\u00d7{h} px")

    def _on_export(self):
        fmt = self._fmt_var.get()
        filters = _FORMAT_FILTERS.get(fmt, [("All files", "*.*")])
        ext = _FORMAT_EXT.get(fmt, ".png")
        path = filedialog.asksaveasfilename(
            parent=self, filetypes=filters, defaultextension=ext
        )
        if not path:
            return

        frame_idx = self._timeline.current_index
        if fmt in _SINGLE_FRAME_FORMATS and self._frame_var.get() == "all":
            frame_idx = -1  # signal "all frames" — caller handles

        layer = None
        if fmt in _LAYER_FORMATS:
            layer_val = self._layer_var.get()
            if layer_val != "All (flattened)":
                layer = layer_val

        # Tag range (only for multi-frame formats)
        tag_start = None
        tag_end = None
        if fmt in _TAG_FORMATS:
            tag_val = self._tag_var.get()
            if tag_val != "All Frames":
                for tag in self._timeline.tags:
                    label = f"{tag['name']} ({tag['start']+1}-{tag['end']+1})"
                    if label == tag_val:
                        tag_start = tag["start"]
                        tag_end = tag["end"]
                        break

        self.result = ExportSettings(
            format=fmt,
            scale=self._scale_var.get(),
            frame=frame_idx,
            layer=layer,
            columns=self._col_var.get(),
            output_path=path,
            tag_start=tag_start,
            tag_end=tag_end,
        )
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()
