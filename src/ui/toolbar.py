"""Left-side icon-only tool bar."""
from __future__ import annotations
import tkinter as tk
from PIL import ImageTk
from src.ui.theme import (
    BG_DEEP, BG_PANEL, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, BUTTON_BG, BUTTON_HOVER,
)
from src.ui.icons import IconPipeline, TOOL_ICON_MAP
from src.keybindings import DEFAULT_BINDINGS

# Human-readable labels for special key names
_KEY_DISPLAY = {
    "bracketleft": "[",
    "bracketright": "]",
    "plus": "+",
    "minus": "-",
}

# Ordered list of tools
TOOL_LIST = list(TOOL_ICON_MAP.keys())

# Backward compat: map capitalized names to lowercase
_COMPAT_MAP = {name.capitalize(): name for name in TOOL_LIST}


class Toolbar(tk.Frame):
    def __init__(self, parent, on_tool_change=None, keybindings=None, **kwargs):
        super().__init__(parent, bg=BG_DEEP, width=48, **kwargs)
        self.pack_propagate(False)

        self._on_tool_change = on_tool_change
        self._active_tool = "pen"
        self._keybindings = keybindings
        self._buttons: dict[str, tk.Button] = {}
        self._photos: dict[str, ImageTk.PhotoImage] = {}
        self._photos_glow: dict[str, ImageTk.PhotoImage] = {}

        self._pipeline = IconPipeline(icon_size=16, display_size=32)

        # Scrollable canvas wrapper so buttons don't get clipped on small windows
        self._scroll_canvas = tk.Canvas(
            self, bg=BG_DEEP, highlightthickness=0, width=48, bd=0
        )
        self._scroll_canvas.pack(fill="both", expand=True)

        self._inner_frame = tk.Frame(self._scroll_canvas, bg=BG_DEEP)
        self._canvas_window = self._scroll_canvas.create_window(
            (0, 0), window=self._inner_frame, anchor="nw"
        )

        # Keep scrollregion in sync with inner frame size
        self._inner_frame.bind("<Configure>", self._on_inner_configure)
        # Keep inner frame width matched to canvas width
        self._scroll_canvas.bind("<Configure>", self._on_canvas_configure)
        # Mouse-wheel scrolling on canvas itself
        self._scroll_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._inner_frame.bind("<MouseWheel>", self._on_mousewheel)

        # Build icon buttons
        for tool_name in TOOL_LIST:
            normal_img, glow_img = self._pipeline.get_icon(tool_name)
            photo_normal = ImageTk.PhotoImage(normal_img)
            photo_glow = ImageTk.PhotoImage(glow_img)
            self._photos[tool_name] = photo_normal
            self._photos_glow[tool_name] = photo_glow

            btn = tk.Button(
                self._inner_frame, image=photo_normal, width=36, height=36,
                bg=BUTTON_BG, activebackground=BUTTON_HOVER,
                relief="flat", bd=0,
                command=lambda n=tool_name: self.select_tool(n)
            )
            btn.pack(padx=4, pady=2)
            self._buttons[tool_name] = btn

            # Tooltip on hover
            btn.bind("<Enter>", lambda e, n=tool_name: self._show_tooltip(e, n))
            btn.bind("<Leave>", lambda e: self._hide_tooltip())
            # Mouse-wheel forwarding from each button
            btn.bind("<MouseWheel>", self._on_mousewheel)

        self._tooltip = None
        self._highlight("pen")

    # ------------------------------------------------------------------
    # Scroll helpers
    # ------------------------------------------------------------------

    def _on_inner_configure(self, event=None):
        self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))

    def _on_canvas_configure(self, event=None):
        if event:
            self._scroll_canvas.itemconfig(self._canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self._scroll_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def tool_names(self) -> list[str]:
        return list(TOOL_LIST)

    @property
    def active_tool(self) -> str:
        return self._active_tool

    # Backward compat property
    @property
    def current_tool(self) -> str:
        return _COMPAT_MAP.get(self._active_tool, self._active_tool).capitalize()

    @current_tool.setter
    def current_tool(self, value: str):
        self._active_tool = _COMPAT_MAP.get(value, value.lower())

    def select_tool(self, name: str) -> None:
        # Accept both "Pen" and "pen"
        lower_name = _COMPAT_MAP.get(name, name.lower())
        self._active_tool = lower_name
        self._highlight(lower_name)
        if self._on_tool_change:
            # Fire callback with capitalized name for backward compat with app.py
            self._on_tool_change(lower_name.capitalize())

    def _highlight(self, active: str) -> None:
        for tool_name, btn in self._buttons.items():
            if tool_name == active:
                btn.config(image=self._photos_glow[tool_name],
                           bg=BG_DEEP)
            else:
                btn.config(image=self._photos[tool_name],
                           bg=BUTTON_BG)

    def _show_tooltip(self, event, tool_name: str):
        self._hide_tooltip()
        x = event.widget.winfo_rootx() + 44
        y = event.widget.winfo_rooty() + 4
        self._tooltip = tk.Toplevel()
        self._tooltip.wm_overrideredirect(True)
        self._tooltip.wm_geometry(f"+{x}+{y}")

        # Build tooltip text with shortcut key
        text = tool_name.capitalize()
        bindings = self._keybindings.get_all() if self._keybindings else DEFAULT_BINDINGS
        key = bindings.get(tool_name, "")
        if key:
            display_key = _KEY_DISPLAY.get(key, key.upper())
            text = f"{text} ({display_key})"

        label = tk.Label(self._tooltip, text=text,
                         bg=BG_PANEL, fg=ACCENT_CYAN,
                         font=("Consolas", 8), padx=6, pady=2,
                         relief="solid", bd=1)
        label.pack()

    def _hide_tooltip(self):
        if self._tooltip:
            self._tooltip.destroy()
            self._tooltip = None

    def add_plugin_tools(self, plugin_tools: dict) -> None:
        """Add plugin tools to the toolbar after a separator."""
        if not plugin_tools:
            return
        sep = tk.Frame(self._inner_frame, bg=BORDER, height=2)
        sep.pack(fill="x", padx=4, pady=4)
        sep.bind("<MouseWheel>", self._on_mousewheel)
        for name, tool in plugin_tools.items():
            btn = tk.Button(
                self._inner_frame, text=name[:3], width=4, height=2,
                bg=BUTTON_BG, activebackground=BUTTON_HOVER,
                fg=TEXT_PRIMARY, font=("Consolas", 8, "bold"),
                relief="flat", bd=0,
                command=lambda n=name: self.select_tool(n)
            )
            btn.pack(padx=4, pady=2)
            self._buttons[name.lower()] = btn
            btn.bind("<Enter>", lambda e, n=name: self._show_tooltip(e, n.lower()))
            btn.bind("<Leave>", lambda e: self._hide_tooltip())
            btn.bind("<MouseWheel>", self._on_mousewheel)

    # --- Backward compat stubs (used by app.py until Task 11 rewires) ---

    @property
    def tool_size(self) -> int:
        return 1

    def _set_size(self, size: int) -> None:
        pass

    def update_symmetry_label(self, mode: str):
        pass

    def update_dither_label(self, pattern: str):
        pass

    def update_pixel_perfect_label(self, enabled: bool):
        pass
