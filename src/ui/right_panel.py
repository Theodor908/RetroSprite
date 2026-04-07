"""Right-side panel with collapsible sections for palette, color picker, preview, compression."""
from __future__ import annotations
import colorsys
import tkinter as tk
from PIL import Image, ImageTk
from src.canvas import build_render_image
from src.palette import Palette
from src.ui.theme import (
    BG_DEEP, BG_PANEL, BG_PANEL_ALT, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, ACCENT_MAGENTA, ACCENT_PURPLE, BUTTON_BG, BUTTON_HOVER,
    style_button, style_listbox, style_text, style_spinbox, style_scale,
    blend_color,
)
from src.ui.tiles_panel import TilesPanel


class CollapsibleSection(tk.Frame):
    """A section with a clickable header that expands/collapses its content."""

    def __init__(self, parent, title="Section", accent_color=ACCENT_CYAN,
                 expanded=True, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self.is_expanded = expanded
        self._accent_color = accent_color

        # Header bar
        self._header = tk.Frame(self, bg=BG_PANEL, cursor="hand2")
        self._header.pack(fill="x")

        # Left accent line (2px)
        self._accent_line = tk.Frame(self._header, width=2, bg=accent_color)
        self._accent_line.pack(side="left", fill="y")

        # Arrow + title
        self._arrow_var = tk.StringVar(value="\u25BC" if expanded else "\u25B6")
        self._arrow = tk.Label(self._header, textvariable=self._arrow_var,
                               fg=accent_color, bg=BG_PANEL,
                               font=("Consolas", 8))
        self._arrow.pack(side="left", padx=(4, 2))

        self._title_label = tk.Label(self._header, text=title,
                                     fg=accent_color, bg=BG_PANEL,
                                     font=("Consolas", 9, "bold"))
        self._title_label.pack(side="left")

        # Click to toggle
        for widget in (self._header, self._arrow, self._title_label):
            widget.bind("<Button-1>", lambda e: self.toggle())

        # Content frame
        self.content = tk.Frame(self, bg=BG_PANEL)
        if expanded:
            self.content.pack(fill="x", padx=(4, 0))

    def toggle(self):
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            self.content.pack(fill="x", padx=(4, 0))
            self._arrow_var.set("\u25BC")
        else:
            self.content.pack_forget()
            self._arrow_var.set("\u25B6")


class PalettePanel(tk.Frame):
    def __init__(self, parent, palette: Palette, on_color_select=None, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self.palette = palette
        self._on_color_select = on_color_select

        self.color_frame = tk.Frame(self, bg=BG_PANEL)
        self.color_frame.pack(padx=4)
        self._color_buttons = []
        self._build_colors()

        self.current_label = tk.Label(self, text="Current:", fg=TEXT_SECONDARY,
                                      bg=BG_PANEL, font=("Consolas", 8))
        self.current_label.pack(pady=(4, 0))
        self.current_swatch = tk.Canvas(self, width=40, height=40,
                                        bg="#000", highlightthickness=1,
                                        highlightbackground=BORDER)
        self.current_swatch.pack(pady=4)
        self._update_swatch()

    def _build_colors(self):
        for widget in self._color_buttons:
            widget.destroy()
        self._color_buttons.clear()

        cols = 4
        for i, color in enumerate(self.palette.colors):
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            btn = tk.Button(
                self.color_frame, bg=hex_color, width=2, height=1,
                relief="flat", activebackground=hex_color,
                command=lambda idx=i: self._select(idx)
            )
            btn.grid(row=i // cols, column=i % cols, padx=1, pady=1)
            self._color_buttons.append(btn)

    def _select(self, index: int):
        self.palette.select(index)
        self._update_swatch()
        if self._on_color_select:
            self._on_color_select(self.palette.selected_color)

    def _update_swatch(self):
        c = self.palette.selected_color
        hex_c = f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
        self.current_swatch.config(bg=hex_c)

    def refresh(self):
        self._build_colors()
        self._update_swatch()


class ColorPickerPanel(tk.Frame):
    """HSV color picker with gradient canvas, brightness slider, and hex input."""

    GRADIENT_SIZE = 150

    def __init__(self, parent, on_color_pick=None, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self._on_color_pick = on_color_pick
        self._current_color = (0, 0, 0, 255)
        self._photo_image = None  # prevent GC

        # Gradient canvas + value slider side by side
        picker_frame = tk.Frame(self, bg=BG_PANEL)
        picker_frame.pack(padx=4, pady=2)

        sz = self.GRADIENT_SIZE
        self._picker_canvas = tk.Canvas(
            picker_frame, width=sz, height=sz, bg="#000",
            highlightthickness=1, highlightbackground=BORDER, cursor="crosshair"
        )
        self._picker_canvas.pack(side="left")
        # Only update preview on drag, fire callback on release
        self._picker_canvas.bind("<Button-1>", self._on_pick_click)
        self._picker_canvas.bind("<B1-Motion>", self._on_pick_drag)
        self._picker_canvas.bind("<ButtonRelease-1>", self._on_pick_release)

        self._value_var = tk.IntVar(value=100)
        self._value_slider = tk.Scale(
            picker_frame, from_=100, to=0, orient="vertical",
            variable=self._value_var, command=self._on_value_change,
            bg=BG_PANEL, fg=TEXT_PRIMARY, troughcolor=BG_PANEL_ALT,
            highlightthickness=0, length=sz, width=15,
            activebackground=ACCENT_CYAN
        )
        self._value_slider.pack(side="left", padx=(4, 0))

        # Preview swatch + hex entry
        bottom = tk.Frame(self, bg=BG_PANEL)
        bottom.pack(fill="x", padx=4, pady=4)

        self._preview = tk.Canvas(
            bottom, width=30, height=20, bg="#000",
            highlightthickness=1, highlightbackground=BORDER
        )
        self._preview.pack(side="left")

        self._hex_var = tk.StringVar(value="#000000")
        hex_entry = tk.Entry(
            bottom, textvariable=self._hex_var, width=8,
            bg=BG_PANEL_ALT, fg=TEXT_PRIMARY, font=("Consolas", 8),
            insertbackground=ACCENT_CYAN, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=ACCENT_CYAN
        )
        hex_entry.pack(side="left", padx=4)
        hex_entry.bind("<Return>", self._on_hex_enter)

        tk.Button(
            bottom, text="+ Palette", bg=BUTTON_BG, fg=TEXT_PRIMARY,
            activebackground=BUTTON_HOVER, activeforeground=TEXT_PRIMARY,
            font=("Consolas", 8), relief="flat",
            command=self._add_to_palette
        ).pack(side="left", padx=2)

        self._render_gradient()

    def _render_gradient(self):
        sz = self.GRADIENT_SIZE
        v = self._value_var.get() / 100.0
        pixels = []
        for y in range(sz):
            s = 1.0 - y / sz
            for x in range(sz):
                h = x / sz
                r, g, b = colorsys.hsv_to_rgb(h, s, v)
                pixels.append((int(r * 255), int(g * 255), int(b * 255)))
        img = Image.new("RGB", (sz, sz))
        img.putdata(pixels)
        self._photo_image = ImageTk.PhotoImage(img)
        self._picker_canvas.delete("all")
        self._picker_canvas.create_image(0, 0, anchor="nw",
                                          image=self._photo_image)

    def _color_at(self, event):
        sz = self.GRADIENT_SIZE
        x = max(0, min(sz - 1, event.x))
        y = max(0, min(sz - 1, event.y))
        h = x / sz
        s = 1.0 - y / sz
        v = self._value_var.get() / 100.0
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return (int(r * 255), int(g * 255), int(b * 255), 255)

    def _on_pick_click(self, event):
        self._current_color = self._color_at(event)
        self._update_preview()

    def _on_pick_drag(self, event):
        # Only update preview during drag, don't fire callback
        self._current_color = self._color_at(event)
        self._update_preview()

    def _on_pick_release(self, event):
        self._current_color = self._color_at(event)
        self._update_preview()
        if self._on_color_pick:
            self._on_color_pick(self._current_color)

    def _on_value_change(self, _val):
        self._render_gradient()

    def _on_hex_enter(self, _event):
        hex_str = self._hex_var.get().strip()
        if hex_str.startswith("#") and len(hex_str) == 7:
            try:
                r = int(hex_str[1:3], 16)
                g = int(hex_str[3:5], 16)
                b = int(hex_str[5:7], 16)
                self._current_color = (r, g, b, 255)
                self._update_preview()
                if self._on_color_pick:
                    self._on_color_pick(self._current_color)
            except ValueError:
                pass

    def _add_to_palette(self):
        if self._on_color_pick:
            self._on_color_pick(self._current_color, add_to_palette=True)

    def _update_preview(self):
        r, g, b, _a = self._current_color
        hex_c = f"#{r:02x}{g:02x}{b:02x}"
        self._preview.config(bg=hex_c)
        self._hex_var.set(hex_c)


class AnimationPreview(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)

        self.preview_canvas = tk.Canvas(self, height=160,
                                        bg=BG_PANEL_ALT, highlightthickness=1,
                                        highlightbackground=BORDER)
        self.preview_canvas.pack(fill="x", padx=4, pady=4)
        self.preview_canvas.bind("<Configure>", self._on_resize)
        self._preview_size = 160

        self._controls_frame = None
        self._preview_photo = None

        # Frame duration control (ms between frames)
        dur_frame = tk.Frame(self, bg=BG_PANEL)
        dur_frame.pack(fill="x", padx=4, pady=(4, 2))
        tk.Label(dur_frame, text="Delay (ms):", fg=TEXT_SECONDARY, bg=BG_PANEL,
                 font=("Consolas", 8)).pack(side="left")
        self.duration_var = tk.IntVar(value=100)
        self.duration_spin = tk.Spinbox(
            dur_frame, from_=20, to=2000, increment=10,
            textvariable=self.duration_var, width=5,
            bg=BG_PANEL_ALT, fg=TEXT_PRIMARY, font=("Consolas", 8),
            buttonbackground=BUTTON_BG
        )
        self.duration_spin.pack(side="left", padx=4)

    @property
    def frame_duration_ms(self) -> int:
        try:
            return max(20, self.duration_var.get())
        except (tk.TclError, ValueError):
            return 100

    def set_callbacks(self, on_play, on_stop, on_cycle_mode=None):
        if self._controls_frame:
            self._controls_frame.destroy()
        self._controls_frame = tk.Frame(self, bg=BG_PANEL)
        self._controls_frame.pack()
        tk.Button(self._controls_frame, text="Play", bg=BUTTON_BG,
                  fg=TEXT_PRIMARY, activebackground=BUTTON_HOVER,
                  activeforeground=TEXT_PRIMARY, font=("Consolas", 8),
                  relief="flat", command=on_play).pack(side="left", padx=2)
        tk.Button(self._controls_frame, text="Stop", bg=BUTTON_BG,
                  fg=TEXT_PRIMARY, activebackground=BUTTON_HOVER,
                  activeforeground=TEXT_PRIMARY, font=("Consolas", 8),
                  relief="flat", command=on_stop).pack(side="left", padx=2)
        if on_cycle_mode:
            self._playback_label = tk.Label(
                self._controls_frame, text="[fwd]", fg=TEXT_SECONDARY,
                bg=BG_PANEL, font=("Consolas", 8), cursor="hand2")
            self._playback_label.pack(side="left", padx=2)
            self._playback_label.bind("<Button-1>",
                                      lambda e: on_cycle_mode())

    def update_playback_label(self, mode: str):
        labels = {"forward": "[fwd]", "reverse": "[rev]", "pingpong": "[pp]"}
        if hasattr(self, '_playback_label'):
            self._playback_label.config(text=labels.get(mode, "[fwd]"))

    def _on_resize(self, event):
        self._preview_size = min(event.width, event.height)

    def render_frame(self, grid, preview_size=None):
        size = preview_size or self._preview_size or 160
        self.preview_canvas.delete("all")
        ps = max(1, size // max(grid.width, grid.height))
        img = build_render_image(grid, pixel_size=ps)
        self._preview_photo = ImageTk.PhotoImage(img)
        # Center the image in the canvas
        cw = self.preview_canvas.winfo_width()
        ch = self.preview_canvas.winfo_height()
        self.preview_canvas.create_image(cw // 2, ch // 2,
                                         image=self._preview_photo,
                                         anchor="center")


class CompressionPanel(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)

        self.stats_text = tk.Text(self, width=22, height=8, bg=BG_PANEL_ALT,
                                  fg=TEXT_PRIMARY, font=("Consolas", 8),
                                  state="disabled", highlightthickness=1,
                                  highlightbackground=BORDER)
        self.stats_text.pack(padx=4, pady=4)

    def update_stats(self, stats: dict):
        self.stats_text.config(state="normal")
        self.stats_text.delete("1.0", "end")
        lines = [
            f"Pixels:     {stats.get('pixel_count', 0)}",
            f"Runs:       {stats.get('run_count', 0)}",
            f"Original:   {stats.get('original_size', 0)} B",
            f"Compressed: {stats.get('compressed_size', 0)} B",
            f"Ratio:      {stats.get('ratio', 0)}x",
        ]
        self.stats_text.insert("1.0", "\n".join(lines))
        self.stats_text.config(state="disabled")


# --- Backward compat classes (used by app.py until Task 11 rewires) ---

class LayerPanel(tk.Frame):
    """Backward compat stub — layers now live in TimelinePanel."""
    def __init__(self, parent, **kwargs):
        # Filter out callback kwargs
        cb_keys = ['on_layer_select', 'on_add', 'on_delete', 'on_duplicate',
                   'on_merge_down', 'on_visibility_toggle', 'on_opacity_change',
                   'on_rename']
        filtered = {k: v for k, v in kwargs.items() if k not in cb_keys}
        super().__init__(parent, bg=BG_PANEL, **filtered)
        self.opacity_var = tk.IntVar(value=100)

    def update_list(self, layers, active_index):
        pass


class FramePanel(tk.Frame):
    """Backward compat stub — frames now live in TimelinePanel."""
    def __init__(self, parent, **kwargs):
        cb_keys = ['on_frame_select', 'on_add', 'on_duplicate', 'on_delete', 'on_rename']
        filtered = {k: v for k, v in kwargs.items() if k not in cb_keys}
        super().__init__(parent, bg=BG_PANEL, **filtered)

    def update_list(self, count, current, tags=None, frame_names=None):
        pass


class RightPanel(tk.Frame):
    def __init__(self, parent, palette=None, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)

        # Scrollable interior
        self._canvas = tk.Canvas(self, bg=BG_PANEL, highlightthickness=0,
                                 width=200)
        from tkinter import ttk
        self._scrollbar = ttk.Scrollbar(self, orient="vertical",
                                        command=self._canvas.yview,
                                        style="Neon.Vertical.TScrollbar")
        self.inner = tk.Frame(self._canvas, bg=BG_PANEL)

        self.inner.bind("<Configure>",
                        lambda e: self._canvas.configure(
                            scrollregion=self._canvas.bbox("all")))
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self.inner, anchor="nw")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<Enter>",
                          lambda e: self._canvas.bind_all("<MouseWheel>",
                                                          self._on_mousewheel))
        self._canvas.bind("<Leave>",
                          lambda e: self._canvas.unbind_all("<MouseWheel>"))

        # --- Collapsible sections ---
        _p = self.inner

        # Palette section
        self.palette_section = CollapsibleSection(_p, title="Palette",
                                                  accent_color=ACCENT_CYAN)
        self.palette_section.pack(fill="x", pady=(0, 2))
        if palette:
            self.palette_panel = PalettePanel(self.palette_section.content, palette)
            self.palette_panel.pack(fill="x")
        else:
            self.palette_panel = None

        # Color Picker section
        self.picker_section = CollapsibleSection(_p, title="Color Picker",
                                                 accent_color=ACCENT_MAGENTA)
        self.picker_section.pack(fill="x", pady=(0, 2))
        self.color_picker = ColorPickerPanel(self.picker_section.content)
        self.color_picker.pack(fill="x")

        # Animation Preview section
        self.preview_section = CollapsibleSection(_p, title="Preview",
                                                  accent_color=ACCENT_PURPLE)
        self.preview_section.pack(fill="x", pady=(0, 2))
        self.animation_preview = AnimationPreview(self.preview_section.content)
        self.animation_preview.pack(fill="x")

        # Tiles panel (visible only when a TilemapLayer is active)
        # app reference is injected later via wire_app(); start hidden
        self.tiles_panel = None  # created when wire_app() is called

    def wire_app(self, app) -> None:
        """Inject the app reference so TilesPanel can access the timeline."""
        if self.tiles_panel is not None:
            return  # already wired
        self.tiles_panel = TilesPanel(self.inner, app)
        # Don't pack yet — update_tiles_visibility() handles show/hide

    def update_tiles_visibility(self, layer) -> None:
        """Show / hide the tiles panel depending on whether *layer* is a tilemap."""
        if self.tiles_panel is None:
            return
        self.tiles_panel.update_visibility(layer)

    def _on_canvas_configure(self, event):
        self._canvas.itemconfigure(self._canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
