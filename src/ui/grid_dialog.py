"""Grid settings dialog for RetroSprite."""
from __future__ import annotations
import tkinter as tk
from src.grid import GridSettings
from src.ui.theme import (
    BG_DEEP, BG_PANEL, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, ACCENT_MAGENTA, BUTTON_BG, BUTTON_HOVER,
)


class RGBAColorPicker(tk.Toplevel):
    """Simple RGBA color picker with 4 sliders."""

    def __init__(self, parent, initial_color: tuple[int, int, int, int]):
        super().__init__(parent)
        self.title("Pick Color")
        self.configure(bg=BG_DEEP)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result: tuple[int, int, int, int] | None = None

        font = ("Consolas", 9)
        self._vars = []
        for i, (label, val) in enumerate([("R:", initial_color[0]),
                                           ("G:", initial_color[1]),
                                           ("B:", initial_color[2]),
                                           ("A:", initial_color[3])]):
            row = tk.Frame(self, bg=BG_DEEP)
            row.pack(fill="x", padx=10, pady=2)
            tk.Label(row, text=label, bg=BG_DEEP, fg=TEXT_PRIMARY,
                     font=font, width=3).pack(side="left")
            var = tk.IntVar(value=val)
            self._vars.append(var)
            scale = tk.Scale(row, from_=0, to=255, orient="horizontal",
                             variable=var, bg=BG_DEEP, fg=TEXT_PRIMARY,
                             troughcolor=BG_PANEL, highlightthickness=0,
                             font=("Consolas", 7), length=200,
                             command=lambda v: self._update_preview())
            scale.pack(side="left", fill="x", expand=True)

        self._preview = tk.Canvas(self, width=60, height=30, bg=BG_DEEP,
                                   highlightthickness=1, highlightbackground=ACCENT_CYAN)
        self._preview.pack(pady=4)
        self._update_preview()

        btn_row = tk.Frame(self, bg=BG_DEEP)
        btn_row.pack(fill="x", pady=(4, 8), padx=10)
        tk.Button(btn_row, text="Cancel", bg=BUTTON_BG, fg=TEXT_PRIMARY,
                  font=font, relief="flat", padx=12,
                  command=self.destroy).pack(side="right", padx=4)
        tk.Button(btn_row, text="OK", bg=ACCENT_CYAN, fg=BG_DEEP,
                  font=("Consolas", 9, "bold"), relief="flat", padx=12,
                  command=self._on_ok).pack(side="right", padx=4)

    def _update_preview(self):
        r, g, b = self._vars[0].get(), self._vars[1].get(), self._vars[2].get()
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        self._preview.configure(bg=hex_color)

    def _on_ok(self):
        self.result = tuple(v.get() for v in self._vars)
        self.destroy()


class GridSettingsDialog(tk.Toplevel):
    """Grid settings dialog for pixel grid and custom grid configuration.

    Usage:
        dialog = GridSettingsDialog(parent, current_grid_settings)
        parent.wait_window(dialog)
        new_settings = dialog.result  # GridSettings or None
    """

    def __init__(self, parent, settings: GridSettings):
        super().__init__(parent)
        self.title("Grid Settings")
        self.configure(bg=BG_DEEP)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._settings = settings
        self.result: GridSettings | None = None

        self._build_ui()

        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _build_ui(self):
        font = ("Consolas", 9)
        pad = {"padx": 10, "pady": 3}
        s = self._settings

        # --- Pixel Grid ---
        tk.Label(self, text="Pixel Grid", bg=BG_DEEP, fg=ACCENT_CYAN,
                 font=("Consolas", 9, "bold")).pack(**pad, anchor="w")

        self._pixel_vis_var = tk.BooleanVar(value=s.pixel_grid_visible)
        tk.Checkbutton(self, text="Visible", variable=self._pixel_vis_var,
                       bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
                       activebackground=BG_DEEP, font=font).pack(padx=20, anchor="w")

        color_row = tk.Frame(self, bg=BG_DEEP)
        color_row.pack(fill="x", padx=20, pady=2)
        tk.Label(color_row, text="Color:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font).pack(side="left")
        self._pixel_color = list(s.pixel_grid_color)
        self._pixel_swatch = tk.Canvas(color_row, width=40, height=18,
                                        highlightthickness=1,
                                        highlightbackground=TEXT_SECONDARY,
                                        cursor="hand2")
        self._pixel_swatch.pack(side="left", padx=8)
        self._pixel_swatch.bind("<Button-1>", lambda e: self._pick_pixel_color())
        self._update_swatch(self._pixel_swatch, self._pixel_color)

        zoom_row = tk.Frame(self, bg=BG_DEEP)
        zoom_row.pack(fill="x", padx=20, pady=2)
        tk.Label(zoom_row, text="Min Zoom:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font).pack(side="left")
        self._pixel_zoom_var = tk.IntVar(value=s.pixel_grid_min_zoom)
        tk.Spinbox(zoom_row, from_=1, to=32, width=4,
                   textvariable=self._pixel_zoom_var, font=font,
                   bg=BG_PANEL, fg=TEXT_PRIMARY,
                   buttonbackground=BUTTON_BG).pack(side="left", padx=4)
        tk.Label(zoom_row, text="px", bg=BG_DEEP, fg=TEXT_SECONDARY,
                 font=font).pack(side="left")

        # Separator
        tk.Frame(self, height=1, bg=ACCENT_CYAN).pack(fill="x", padx=10, pady=6)

        # --- Custom Grid ---
        tk.Label(self, text="Custom Grid", bg=BG_DEEP, fg=ACCENT_CYAN,
                 font=("Consolas", 9, "bold")).pack(**pad, anchor="w")

        self._custom_vis_var = tk.BooleanVar(value=s.custom_grid_visible)
        tk.Checkbutton(self, text="Visible", variable=self._custom_vis_var,
                       bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
                       activebackground=BG_DEEP, font=font).pack(padx=20, anchor="w")

        size_row = tk.Frame(self, bg=BG_DEEP)
        size_row.pack(fill="x", padx=20, pady=2)
        self._custom_w_var = tk.IntVar(value=s.custom_grid_width)
        self._custom_h_var = tk.IntVar(value=s.custom_grid_height)
        tk.Label(size_row, text="Width:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font).pack(side="left")
        tk.Spinbox(size_row, from_=1, to=256, width=4,
                   textvariable=self._custom_w_var, font=font,
                   bg=BG_PANEL, fg=TEXT_PRIMARY,
                   buttonbackground=BUTTON_BG).pack(side="left", padx=4)
        tk.Label(size_row, text="Height:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font).pack(side="left", padx=(8, 0))
        tk.Spinbox(size_row, from_=1, to=256, width=4,
                   textvariable=self._custom_h_var, font=font,
                   bg=BG_PANEL, fg=TEXT_PRIMARY,
                   buttonbackground=BUTTON_BG).pack(side="left", padx=4)

        offset_row = tk.Frame(self, bg=BG_DEEP)
        offset_row.pack(fill="x", padx=20, pady=2)
        self._offset_x_var = tk.IntVar(value=s.custom_grid_offset_x)
        self._offset_y_var = tk.IntVar(value=s.custom_grid_offset_y)
        tk.Label(offset_row, text="Offset X:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font).pack(side="left")
        tk.Spinbox(offset_row, from_=0, to=256, width=4,
                   textvariable=self._offset_x_var, font=font,
                   bg=BG_PANEL, fg=TEXT_PRIMARY,
                   buttonbackground=BUTTON_BG).pack(side="left", padx=4)
        tk.Label(offset_row, text="Offset Y:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font).pack(side="left", padx=(8, 0))
        tk.Spinbox(offset_row, from_=0, to=256, width=4,
                   textvariable=self._offset_y_var, font=font,
                   bg=BG_PANEL, fg=TEXT_PRIMARY,
                   buttonbackground=BUTTON_BG).pack(side="left", padx=4)

        ccolor_row = tk.Frame(self, bg=BG_DEEP)
        ccolor_row.pack(fill="x", padx=20, pady=2)
        tk.Label(ccolor_row, text="Color:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                 font=font).pack(side="left")
        self._custom_color = list(s.custom_grid_color)
        self._custom_swatch = tk.Canvas(ccolor_row, width=40, height=18,
                                         highlightthickness=1,
                                         highlightbackground=TEXT_SECONDARY,
                                         cursor="hand2")
        self._custom_swatch.pack(side="left", padx=8)
        self._custom_swatch.bind("<Button-1>", lambda e: self._pick_custom_color())
        self._update_swatch(self._custom_swatch, self._custom_color)

        # --- Buttons ---
        btn_row = tk.Frame(self, bg=BG_DEEP)
        btn_row.pack(fill="x", pady=(12, 8), padx=10)
        tk.Button(btn_row, text="Cancel", bg=BUTTON_BG, fg=TEXT_PRIMARY,
                  font=font, relief="flat", padx=16, pady=4,
                  command=self._on_cancel).pack(side="right", padx=4)
        tk.Button(btn_row, text="Apply", bg=ACCENT_CYAN, fg=BG_DEEP,
                  font=("Consolas", 9, "bold"), relief="flat", padx=16, pady=4,
                  command=self._on_apply).pack(side="right", padx=4)

    def _update_swatch(self, canvas, color):
        r, g, b = color[0], color[1], color[2]
        canvas.configure(bg=f"#{r:02x}{g:02x}{b:02x}")

    def _pick_pixel_color(self):
        picker = RGBAColorPicker(self, tuple(self._pixel_color))
        self.wait_window(picker)
        if picker.result is not None:
            self._pixel_color = list(picker.result)
            self._update_swatch(self._pixel_swatch, self._pixel_color)

    def _pick_custom_color(self):
        picker = RGBAColorPicker(self, tuple(self._custom_color))
        self.wait_window(picker)
        if picker.result is not None:
            self._custom_color = list(picker.result)
            self._update_swatch(self._custom_swatch, self._custom_color)

    def _on_cancel(self):
        self.result = None
        self.destroy()

    def _on_apply(self):
        self.result = GridSettings(
            pixel_grid_visible=self._pixel_vis_var.get(),
            pixel_grid_color=tuple(self._pixel_color),
            pixel_grid_min_zoom=self._pixel_zoom_var.get(),
            custom_grid_visible=self._custom_vis_var.get(),
            custom_grid_width=max(1, self._custom_w_var.get()),
            custom_grid_height=max(1, self._custom_h_var.get()),
            custom_grid_offset_x=self._offset_x_var.get(),
            custom_grid_offset_y=self._offset_y_var.get(),
            custom_grid_color=tuple(self._custom_color),
        )
        self.destroy()
