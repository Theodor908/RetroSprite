"""Top context-sensitive tool options bar for RetroSprite."""

import tkinter as tk
from src.ui.theme import (
    BG_PANEL, BG_PANEL_ALT, BG_DEEP, BORDER, ACCENT_CYAN, ACCENT_MAGENTA,
    TEXT_PRIMARY, TEXT_SECONDARY, BUTTON_BG, BUTTON_HOVER,
    style_button, style_label, style_frame
)

# Which tools show which controls
TOOL_OPTIONS = {
    "pen":     {"size": True, "symmetry": True, "dither": True, "pixel_perfect": True, "ink_mode": True},
    "eraser":  {"size": True, "symmetry": True, "pixel_perfect": True, "ink_mode": True},
    "blur":    {"size": True},
    "fill":    {"tolerance": True, "dither": True, "fill_mode": True},
    "ellipse": {"size": True},
    "pick":    {},
    "select":  {},
    "wand":    {"tolerance": True},
    "line":    {"size": True},
    "rect":    {"size": True},
    "move":    {},
    "hand":    {},
    "lasso":   {},
    "polygon": {"size": True},
    "roundrect": {"size": True, "corner_radius": True},
    "text": {"font_name": True, "font_size": True, "spacing": True, "line_height": True, "align": True},
}


class OptionsBar(tk.Frame):
    """Context-sensitive tool options bar displayed below the menu bar."""

    def __init__(self, parent, on_size_change=None, on_symmetry_change=None,
                 on_dither_change=None, on_pixel_perfect_toggle=None,
                 on_tolerance_change=None, on_ink_mode_change=None,
                 on_radius_change=None, on_fill_mode_change=None):
        super().__init__(parent, bg=BG_PANEL, height=36)
        self.pack_propagate(False)

        self.current_tool = "pen"
        self._on_size_change = on_size_change
        self._on_symmetry_change = on_symmetry_change
        self._on_dither_change = on_dither_change
        self._on_pixel_perfect_toggle = on_pixel_perfect_toggle
        self._on_tolerance_change = on_tolerance_change
        self._on_ink_mode_change = on_ink_mode_change
        self._on_radius_change = on_radius_change
        self._on_fill_mode_change = on_fill_mode_change

        # Tool indicator
        self._tool_label = tk.Label(self, text="Pen", font=("Consolas", 9, "bold"),
                                    bg=BG_PANEL, fg=ACCENT_CYAN)
        self._tool_label.pack(side="left", padx=(8, 16))

        # Separator
        sep = tk.Frame(self, width=1, bg=ACCENT_CYAN)
        sep.pack(side="left", fill="y", pady=4)

        # Size controls
        self._size_frame = tk.Frame(self, bg=BG_PANEL)
        tk.Label(self._size_frame, text="Size:", font=("Consolas", 8),
                 bg=BG_PANEL, fg=TEXT_SECONDARY).pack(side="left", padx=(8, 2))
        self._size_var = tk.IntVar(value=1)
        btn_minus = tk.Button(self._size_frame, text="-", width=2, font=("Consolas", 8),
                              bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                              command=lambda: self._change_size(-1))
        btn_minus.pack(side="left")
        self._size_entry = tk.Entry(self._size_frame, textvariable=self._size_var,
                                    font=("Consolas", 9, "bold"), bg=BG_PANEL_ALT,
                                    fg=TEXT_PRIMARY, width=3, justify="center",
                                    insertbackground=ACCENT_CYAN,
                                    highlightthickness=1, highlightbackground=BORDER,
                                    highlightcolor=ACCENT_CYAN, relief="flat")
        self._size_entry.pack(side="left")
        self._size_entry.bind("<Return>", lambda e: self._commit_size())
        self._size_entry.bind("<FocusOut>", lambda e: self._commit_size())
        btn_plus = tk.Button(self._size_frame, text="+", width=2, font=("Consolas", 8),
                             bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                             command=lambda: self._change_size(1))
        btn_plus.pack(side="left")

        # Symmetry dropdown
        self._sym_frame = tk.Frame(self, bg=BG_PANEL)
        tk.Label(self._sym_frame, text="Sym:", font=("Consolas", 8),
                 bg=BG_PANEL, fg=TEXT_SECONDARY).pack(side="left", padx=(8, 2))
        self._sym_var = tk.StringVar(value="off")
        self._sym_options = ["off", "horizontal", "vertical", "both"]
        self._sym_btn = tk.Button(self._sym_frame, textvariable=self._sym_var,
                                  width=8, font=("Consolas", 8),
                                  bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                                  command=self._cycle_symmetry)
        self._sym_btn.pack(side="left")

        # Dither dropdown
        self._dither_frame = tk.Frame(self, bg=BG_PANEL)
        tk.Label(self._dither_frame, text="Dither:", font=("Consolas", 8),
                 bg=BG_PANEL, fg=TEXT_SECONDARY).pack(side="left", padx=(8, 2))
        self._dither_var = tk.StringVar(value="none")
        self._dither_btn = tk.Button(self._dither_frame, textvariable=self._dither_var,
                                     width=8, font=("Consolas", 8),
                                     bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                                     command=self._cycle_dither)
        self._dither_btn.pack(side="left")

        # Pixel Perfect toggle
        self._pp_frame = tk.Frame(self, bg=BG_PANEL)
        self._pp_var = tk.BooleanVar(value=False)
        self._pp_btn = tk.Button(self._pp_frame, text="PP: Off", width=6,
                                 font=("Consolas", 8),
                                 bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                                 command=self._toggle_pp)
        self._pp_btn.pack(side="left", padx=(8, 0))

        # Ink mode cycle button
        self._ink_frame = tk.Frame(self, bg=BG_PANEL)
        self._ink_var = tk.StringVar(value="Normal")
        self._ink_btn = tk.Button(self._ink_frame, text="Ink: Normal", width=12,
                                  font=("Consolas", 8),
                                  bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                                  command=self._cycle_ink_mode)
        self._ink_btn.pack(side="left", padx=(8, 0))

        # Tolerance controls
        self._tol_frame = tk.Frame(self, bg=BG_PANEL)
        tk.Label(self._tol_frame, text="Tol:", font=("Consolas", 8),
                 bg=BG_PANEL, fg=TEXT_SECONDARY).pack(side="left", padx=(8, 2))
        self._tol_var = tk.IntVar(value=32)
        tk.Button(self._tol_frame, text="-", width=2, font=("Consolas", 8),
                  bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                  command=lambda: self._change_tolerance(-8)).pack(side="left")
        tk.Label(self._tol_frame, textvariable=self._tol_var,
                 font=("Consolas", 9, "bold"), bg=BG_PANEL, fg=TEXT_PRIMARY,
                 width=3).pack(side="left")
        tk.Button(self._tol_frame, text="+", width=2, font=("Consolas", 8),
                  bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                  command=lambda: self._change_tolerance(8)).pack(side="left")

        # Corner radius controls
        self._radius_frame = tk.Frame(self, bg=BG_PANEL)
        tk.Label(self._radius_frame, text="Radius:", font=("Consolas", 8),
                 bg=BG_PANEL, fg=TEXT_SECONDARY).pack(side="left", padx=(8, 2))
        self._radius_var = tk.IntVar(value=2)
        tk.Button(self._radius_frame, text="-", width=2, font=("Consolas", 8),
                  bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                  command=lambda: self._change_radius(-1)).pack(side="left")
        tk.Label(self._radius_frame, textvariable=self._radius_var,
                 font=("Consolas", 9, "bold"), bg=BG_PANEL, fg=TEXT_PRIMARY,
                 width=3).pack(side="left")
        tk.Button(self._radius_frame, text="+", width=2, font=("Consolas", 8),
                  bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                  command=lambda: self._change_radius(1)).pack(side="left")

        # Fill mode toggle
        self._fill_mode_frame = tk.Frame(self, bg=BG_PANEL)
        self._fill_mode_var = tk.StringVar(value="normal")
        self._fill_mode_btn = tk.Button(
            self._fill_mode_frame, text="Fill: Normal", width=12,
            font=("Consolas", 8),
            bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
            command=self._on_fill_mode_toggle)
        self._fill_mode_btn.pack(side="left", padx=(8, 0))

        # Bottom gradient border (cyan -> purple)
        self._border_canvas = tk.Canvas(self, height=2, bg=BG_PANEL,
                                        highlightthickness=0)
        self._border_canvas.pack(side="bottom", fill="x")
        self._border_canvas.bind("<Configure>", self._draw_gradient_border)

        self.set_tool("pen")

    def _draw_gradient_border(self, event=None):
        c = self._border_canvas
        c.delete("all")
        w = c.winfo_width()
        if w < 2:
            return
        from src.ui.theme import blend_color, ACCENT_PURPLE
        steps = min(w, 200)
        seg_w = w / steps
        for i in range(steps):
            color = blend_color(ACCENT_CYAN, ACCENT_PURPLE, i / max(1, steps - 1))
            x1 = int(i * seg_w)
            x2 = int((i + 1) * seg_w) + 1
            c.create_rectangle(x1, 0, x2, 2, fill=color, outline="")

    _INK_MODES = ["Normal", "\u03b1Lock", "Behind"]

    def _cycle_ink_mode(self):
        current = self._ink_var.get()
        idx = self._INK_MODES.index(current) if current in self._INK_MODES else 0
        new_mode = self._INK_MODES[(idx + 1) % len(self._INK_MODES)]
        self._ink_var.set(new_mode)
        self._ink_btn.config(text=f"Ink: {new_mode}")
        if self._on_ink_mode_change:
            mode_map = {"Normal": "normal", "\u03b1Lock": "alpha_lock", "Behind": "behind"}
            self._on_ink_mode_change(mode_map[new_mode])

    def set_tool(self, tool_name: str):
        """Update the options bar for the given tool."""
        self.current_tool = tool_name
        self._tool_label.config(text=tool_name.capitalize())
        opts = TOOL_OPTIONS.get(tool_name, {})

        # Show/hide control frames
        for frame, key in [
            (self._size_frame, "size"),
            (self._sym_frame, "symmetry"),
            (self._dither_frame, "dither"),
            (self._pp_frame, "pixel_perfect"),
            (self._ink_frame, "ink_mode"),
            (self._tol_frame, "tolerance"),
            (self._radius_frame, "corner_radius"),
            (self._fill_mode_frame, "fill_mode"),
        ]:
            if opts.get(key):
                frame.pack(side="left", padx=2)
            else:
                frame.pack_forget()

    def get_size(self) -> int:
        return self._size_var.get()

    def set_size(self, size: int):
        self._size_var.set(max(1, min(99, size)))

    def get_symmetry(self) -> str:
        return self._sym_var.get()

    def set_symmetry(self, mode: str):
        self._sym_var.set(mode)

    def get_tolerance(self) -> int:
        return self._tol_var.get()

    def _commit_size(self):
        try:
            val = int(self._size_entry.get())
        except ValueError:
            val = 1
        new = max(1, min(99, val))
        self._size_var.set(new)
        if self._on_size_change:
            self._on_size_change(new)

    def _change_size(self, delta):
        new = max(1, min(99, self._size_var.get() + delta))
        self._size_var.set(new)
        if self._on_size_change:
            self._on_size_change(new)

    def _cycle_symmetry(self):
        idx = self._sym_options.index(self._sym_var.get())
        new_mode = self._sym_options[(idx + 1) % len(self._sym_options)]
        self._sym_var.set(new_mode)
        if self._on_symmetry_change:
            self._on_symmetry_change(new_mode)

    def _cycle_dither(self):
        if self._on_dither_change:
            self._on_dither_change()

    def _toggle_pp(self):
        self._pp_var.set(not self._pp_var.get())
        self._pp_btn.config(text=f"PP: {'On' if self._pp_var.get() else 'Off'}")
        if self._on_pixel_perfect_toggle:
            self._on_pixel_perfect_toggle()

    def _change_radius(self, delta):
        new = max(0, min(50, self._radius_var.get() + delta))
        self._radius_var.set(new)
        if self._on_radius_change:
            self._on_radius_change(new)

    def get_radius(self) -> int:
        return self._radius_var.get()

    def set_radius(self, radius: int):
        self._radius_var.set(max(0, min(50, radius)))

    def _change_tolerance(self, delta):
        new = max(0, min(255, self._tol_var.get() + delta))
        self._tol_var.set(new)
        if self._on_tolerance_change:
            self._on_tolerance_change(new)

    def _on_fill_mode_toggle(self):
        current = self._fill_mode_var.get()
        new_mode = "contour" if current == "normal" else "normal"
        self._fill_mode_var.set(new_mode)
        display = "Contour" if new_mode == "contour" else "Normal"
        self._fill_mode_btn.config(text=f"Fill: {display}")
        if self._on_fill_mode_change:
            self._on_fill_mode_change(new_mode)

    def get_fill_mode(self) -> str:
        return self._fill_mode_var.get()

    def set_fill_mode(self, mode: str):
        self._fill_mode_var.set(mode)
        display = "Contour" if mode == "contour" else "Normal"
        self._fill_mode_btn.config(text=f"Fill: {display}")

    def update_dither_label(self, name: str):
        self._dither_var.set(name)

    def update_symmetry_label(self, mode: str):
        self._sym_var.set(mode)

    def update_pixel_perfect_label(self, on: bool):
        self._pp_var.set(on)
        self._pp_btn.config(text=f"PP: {'On' if on else 'Off'}")

    def restore_settings(self, settings: dict) -> None:
        """Batch-update all UI controls from a settings dict.
        Called on tool switch to reflect the new tool's stored values."""
        if "size" in settings:
            self._size_var.set(settings["size"])
        if "symmetry" in settings:
            self._sym_var.set(settings["symmetry"])
        if "dither" in settings:
            self._dither_var.set(settings["dither"])
        if "pixel_perfect" in settings:
            self._pp_var.set(settings["pixel_perfect"])
            self._pp_btn.config(text=f"PP: {'On' if settings['pixel_perfect'] else 'Off'}")
        if "ink_mode" in settings:
            mode_display = {"normal": "Normal", "alpha_lock": "\u03b1Lock", "behind": "Behind"}
            display = mode_display.get(settings["ink_mode"], "Normal")
            self._ink_var.set(display)
            self._ink_btn.config(text=f"Ink: {display}")
        if "tolerance" in settings:
            self._tol_var.set(settings["tolerance"])
        if "corner_radius" in settings:
            self._radius_var.set(settings["corner_radius"])
        if "fill_mode" in settings:
            self.set_fill_mode(settings["fill_mode"])
