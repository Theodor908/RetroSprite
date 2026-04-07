# Grid System Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded grid overlay with a configurable dual-grid system (pixel grid + custom NxM grid), each independently toggleable with RGBA colors, accessible via toolbar, menu, and keyboard shortcuts, persisted per-project.

**Architecture:** New `GridSettings` dataclass in `src/grid.py` holds all state. `build_render_image()` in `canvas.py` accepts grid settings instead of a bool. A new `GridSettingsDialog` in `src/ui/grid_dialog.py` provides the configuration UI. Grid state is serialized into `.retro` project files via `project.py`. The options bar gets a grid widget for quick toggle/access.

**Tech Stack:** Python 3.8+, Tkinter, Pillow (ImageDraw), dataclasses

**Spec:** `docs/superpowers/specs/2026-04-07-grid-system-design.md`

---

### Task 1: GridSettings dataclass

**Files:**
- Create: `src/grid.py`
- Create: `tests/test_grid.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_grid.py`:

```python
"""Tests for grid settings dataclass."""
import pytest
from src.grid import GridSettings


class TestGridSettings:
    def test_defaults(self):
        gs = GridSettings()
        assert gs.pixel_grid_visible is True
        assert gs.pixel_grid_color == (180, 180, 180, 80)
        assert gs.pixel_grid_min_zoom == 4
        assert gs.custom_grid_visible is False
        assert gs.custom_grid_width == 16
        assert gs.custom_grid_height == 16
        assert gs.custom_grid_offset_x == 0
        assert gs.custom_grid_offset_y == 0
        assert gs.custom_grid_color == (0, 240, 255, 120)

    def test_to_dict_roundtrip(self):
        gs = GridSettings(
            pixel_grid_visible=False,
            pixel_grid_color=(255, 0, 0, 200),
            pixel_grid_min_zoom=8,
            custom_grid_visible=True,
            custom_grid_width=32,
            custom_grid_height=24,
            custom_grid_offset_x=4,
            custom_grid_offset_y=8,
            custom_grid_color=(0, 255, 0, 100),
        )
        d = gs.to_dict()
        restored = GridSettings.from_dict(d)
        assert restored == gs

    def test_from_dict_missing_fields(self):
        d = {"pixel_visible": False, "custom_width": 8}
        gs = GridSettings.from_dict(d)
        assert gs.pixel_grid_visible is False
        assert gs.custom_grid_width == 8
        # All other fields should be defaults
        assert gs.pixel_grid_color == (180, 180, 180, 80)
        assert gs.custom_grid_visible is False
        assert gs.custom_grid_height == 16

    def test_from_dict_empty(self):
        gs = GridSettings.from_dict({})
        default = GridSettings()
        assert gs == default

    def test_pixel_grid_color_rgba(self):
        gs = GridSettings()
        assert len(gs.pixel_grid_color) == 4
        assert len(gs.custom_grid_color) == 4

    def test_custom_grid_dimensions_clamped(self):
        gs = GridSettings(custom_grid_width=0, custom_grid_height=-5)
        assert gs.custom_grid_width >= 1
        assert gs.custom_grid_height >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_grid.py -v`
Expected: FAIL — `src.grid` does not exist

- [ ] **Step 3: Implement GridSettings**

Create `src/grid.py`:

```python
"""Grid overlay settings for RetroSprite."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class GridSettings:
    """Dual grid configuration: pixel grid (1x1) + custom grid (NxM)."""

    # Pixel grid (1x1)
    pixel_grid_visible: bool = True
    pixel_grid_color: tuple[int, int, int, int] = (180, 180, 180, 80)
    pixel_grid_min_zoom: int = 4

    # Custom grid (NxM)
    custom_grid_visible: bool = False
    custom_grid_width: int = 16
    custom_grid_height: int = 16
    custom_grid_offset_x: int = 0
    custom_grid_offset_y: int = 0
    custom_grid_color: tuple[int, int, int, int] = (0, 240, 255, 120)

    def __post_init__(self):
        self.custom_grid_width = max(1, self.custom_grid_width)
        self.custom_grid_height = max(1, self.custom_grid_height)

    def to_dict(self) -> dict:
        return {
            "pixel_visible": self.pixel_grid_visible,
            "pixel_color": list(self.pixel_grid_color),
            "pixel_min_zoom": self.pixel_grid_min_zoom,
            "custom_visible": self.custom_grid_visible,
            "custom_width": self.custom_grid_width,
            "custom_height": self.custom_grid_height,
            "custom_offset_x": self.custom_grid_offset_x,
            "custom_offset_y": self.custom_grid_offset_y,
            "custom_color": list(self.custom_grid_color),
        }

    @classmethod
    def from_dict(cls, data: dict) -> GridSettings:
        defaults = cls()
        return cls(
            pixel_grid_visible=data.get("pixel_visible", defaults.pixel_grid_visible),
            pixel_grid_color=tuple(data.get("pixel_color", list(defaults.pixel_grid_color))),
            pixel_grid_min_zoom=data.get("pixel_min_zoom", defaults.pixel_grid_min_zoom),
            custom_grid_visible=data.get("custom_visible", defaults.custom_grid_visible),
            custom_grid_width=data.get("custom_width", defaults.custom_grid_width),
            custom_grid_height=data.get("custom_height", defaults.custom_grid_height),
            custom_grid_offset_x=data.get("custom_offset_x", defaults.custom_grid_offset_x),
            custom_grid_offset_y=data.get("custom_offset_y", defaults.custom_grid_offset_y),
            custom_grid_color=tuple(data.get("custom_color", list(defaults.custom_grid_color))),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_grid.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/grid.py tests/test_grid.py
git commit -m "feat: add GridSettings dataclass with serialization"
```

---

### Task 2: Update canvas rendering for dual grid

**Files:**
- Modify: `src/canvas.py:10-104` (build_render_image function signature + grid rendering)
- Modify: `src/canvas.py:138` (PixelCanvas.show_grid → grid_settings)
- Modify: `src/canvas.py:277-290` (render method)

- [ ] **Step 1: Update `build_render_image` to accept `GridSettings`**

In `src/canvas.py`, change the function signature and grid rendering. Replace:

```python
def build_render_image(grid: PixelGrid, pixel_size: int,
                       show_grid: bool,
```

with:

```python
def build_render_image(grid: PixelGrid, pixel_size: int,
                       grid_settings: 'GridSettings | None' = None,
```

Add at the top of `canvas.py`, after existing imports:

```python
from src.grid import GridSettings
```

Replace the grid rendering block (lines 97-104):

```python
    if show_grid and pixel_size >= 4:
        draw = ImageDraw.Draw(scaled)
        grid_color = (180, 180, 180)
        sw, sh = scaled.size
        for x in range(0, sw + 1, pixel_size):
            draw.line([(x, 0), (x, sh - 1)], fill=grid_color)
        for y in range(0, sh + 1, pixel_size):
            draw.line([(0, y), (sw - 1, y)], fill=grid_color)
```

with:

```python
    gs = grid_settings or GridSettings()
    sw, sh = scaled.size
    draw = ImageDraw.Draw(scaled)

    # Pixel grid (1x1)
    if gs.pixel_grid_visible and pixel_size >= gs.pixel_grid_min_zoom:
        r, g, b, a = gs.pixel_grid_color
        # Blend alpha against dark background (#0d0d12)
        bg_r, bg_g, bg_b = 13, 13, 18
        f = a / 255.0
        pc = (int(bg_r * (1 - f) + r * f),
              int(bg_g * (1 - f) + g * f),
              int(bg_b * (1 - f) + b * f))
        for x in range(0, sw + 1, pixel_size):
            draw.line([(x, 0), (x, sh - 1)], fill=pc)
        for y in range(0, sh + 1, pixel_size):
            draw.line([(0, y), (sw - 1, y)], fill=pc)

    # Custom grid (NxM)
    if gs.custom_grid_visible and gs.custom_grid_width > 0 and gs.custom_grid_height > 0:
        r, g, b, a = gs.custom_grid_color
        bg_r, bg_g, bg_b = 13, 13, 18
        f = a / 255.0
        cc = (int(bg_r * (1 - f) + r * f),
              int(bg_g * (1 - f) + g * f),
              int(bg_b * (1 - f) + b * f))
        gw = gs.custom_grid_width * pixel_size
        gh = gs.custom_grid_height * pixel_size
        ox = gs.custom_grid_offset_x * pixel_size
        oy = gs.custom_grid_offset_y * pixel_size
        # Vertical lines
        start_x = ox % gw if gw > 0 else 0
        x = start_x
        while x <= sw:
            draw.line([(x, 0), (x, sh - 1)], fill=cc, width=2)
            x += gw
        # Horizontal lines
        start_y = oy % gh if gh > 0 else 0
        y = start_y
        while y <= sh:
            draw.line([(0, y), (sw - 1, y)], fill=cc, width=2)
            y += gh
```

- [ ] **Step 2: Update PixelCanvas to use grid_settings**

In `src/canvas.py`, in the `PixelCanvas.__init__` method, replace:

```python
        self.show_grid = True
```

with:

```python
        self.grid_settings = GridSettings()
```

In the `render` method, replace:

```python
        img = build_render_image(self.grid, self.pixel_size, self.show_grid,
```

with:

```python
        img = build_render_image(self.grid, self.pixel_size, self.grid_settings,
```

- [ ] **Step 3: Update ALL callers of `build_render_image`**

The `show_grid` parameter was removed. All callers using it (keyword or positional) must be updated.

In `src/ui/right_panel.py:320`, replace:
```python
        img = build_render_image(grid, pixel_size=ps, show_grid=False)
```
with:
```python
        img = build_render_image(grid, pixel_size=ps)
```

In `tests/test_canvas_rendering.py`, replace ALL occurrences of `show_grid=False` with nothing (remove the parameter), and replace ALL occurrences of `show_grid=True` with `grid_settings=GridSettings()`. Add `from src.grid import GridSettings` to the imports. There are ~19 occurrences. Use find-and-replace:
- `show_grid=False` → remove the parameter entirely (grid_settings defaults to None which means no grid)
- `show_grid=True` → `grid_settings=GridSettings()`

In `tests/test_tiled_mode.py`, replace positional `False` (the 3rd argument to `build_render_image`) with `None`. Add `from src.grid import GridSettings` if needed for any `True` cases.

- [ ] **Step 4: Verify all tests pass**

Run: `python -m pytest tests/ -x -q`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/canvas.py src/ui/right_panel.py tests/test_canvas_rendering.py tests/test_tiled_mode.py
git commit -m "feat: replace hardcoded grid with configurable dual-grid rendering"
```

---

### Task 3: Update app.py and file_ops.py for grid integration

**Files:**
- Modify: `src/app.py` (init, render calls, View menu items, keyboard bindings)
- Modify: `src/file_ops.py` (grid toggle/settings methods — per CLAUDE.md, methods go in mixins, not app.py)

- [ ] **Step 1: Add grid_settings initialization**

In `src/app.py`, add import near the top (alongside other src imports):

```python
from src.grid import GridSettings
```

In `__init__`, near the other state variables (around line 169 where `self._tiled_mode = "off"` is), add:

```python
        self._grid_settings = GridSettings()
```

- [ ] **Step 2: Pass grid_settings to canvas**

In `_refresh_canvas` and `_render_canvas` methods, after setting `self.pixel_canvas.grid`, add before the `render()` call:

```python
        self.pixel_canvas.grid_settings = self._grid_settings
```

This needs to be added in both `_refresh_canvas` (around line 890) and `_render_canvas` (around line 900).

- [ ] **Step 3: Add View menu items and keyboard shortcuts**

In `_build_menu`, in the View menu section (around line 363), BEFORE the Tiled mode entries, add:

```python
        view_menu.add_checkbutton(label="Show Pixel Grid",
                                  variable=self._pixel_grid_var,
                                  command=self._toggle_pixel_grid,
                                  accelerator="Ctrl+H")
        view_menu.add_checkbutton(label="Show Custom Grid",
                                  variable=self._custom_grid_var,
                                  command=self._toggle_custom_grid,
                                  accelerator="Ctrl+G")
        view_menu.add_command(label="Grid Settings...",
                              command=self._show_grid_settings,
                              accelerator="Ctrl+Shift+G")
        view_menu.add_separator()
```

In `__init__`, add the tk variables (near other variable declarations):

```python
        self._pixel_grid_var = tk.BooleanVar(value=True)
        self._custom_grid_var = tk.BooleanVar(value=False)
```

In the keyboard bindings section (around line 558), add:

```python
        self.root.bind("<Control-g>", lambda e: self._toggle_custom_grid())
        self.root.bind("<Control-h>", lambda e: self._toggle_pixel_grid())
        self.root.bind("<Control-Shift-G>", lambda e: self._show_grid_settings())
```

- [ ] **Step 4: Add toggle and settings methods to FileOpsMixin**

Per CLAUDE.md ("Do NOT add methods to `src/app.py`"), these methods go in `src/file_ops.py` (FileOpsMixin). Add them after the existing reference image methods:

```python
    # ------------------------------------------------------------------
    # Grid settings
    # ------------------------------------------------------------------

    def _toggle_pixel_grid(self):
        self._grid_settings.pixel_grid_visible = self._pixel_grid_var.get()
        self._render_canvas()

    def _toggle_custom_grid(self):
        self._grid_settings.custom_grid_visible = self._custom_grid_var.get()
        self._update_grid_widget()
        self._render_canvas()

    def _quick_toggle_custom_grid(self):
        self._grid_settings.custom_grid_visible = not self._grid_settings.custom_grid_visible
        self._custom_grid_var.set(self._grid_settings.custom_grid_visible)
        self._update_grid_widget()
        self._render_canvas()

    def _show_grid_settings(self):
        from src.ui.grid_dialog import GridSettingsDialog
        dialog = GridSettingsDialog(self.root, self._grid_settings)
        self.root.wait_window(dialog)
        if dialog.result is not None:
            self._grid_settings = dialog.result
            self._pixel_grid_var.set(self._grid_settings.pixel_grid_visible)
            self._custom_grid_var.set(self._grid_settings.custom_grid_visible)
            self._update_grid_widget()
            self._render_canvas()

    def _update_grid_widget(self):
        gs = self._grid_settings
        if gs.custom_grid_visible:
            text = f"Grid: {gs.custom_grid_width}\u00d7{gs.custom_grid_height}"
        else:
            text = "Grid: Off"
        if hasattr(self, '_grid_widget_label'):
            self._grid_widget_label.config(text=text)
```

- [ ] **Step 5: Verify app launches and grids render**

Run: `python -m pytest tests/ -x -q`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/app.py
git commit -m "feat: add grid toggle/settings to View menu with keyboard shortcuts"
```

---

### Task 4: Grid toolbar widget

**Files:**
- Modify: `src/app.py` (add widget to options bar area)

- [ ] **Step 1: Add grid widget to the options bar**

In `src/app.py`, after the `options_bar.pack()` call (around line 499), add the grid widget. This is a small label packed into the right side of the options bar:

```python
        # Grid widget (right side of options bar)
        self._grid_widget_label = tk.Label(
            self.options_bar, text="Grid: Off",
            font=("Consolas", 8), bg=BG_PANEL, fg=TEXT_SECONDARY,
            cursor="hand2", padx=8)
        self._grid_widget_label.pack(side="right", padx=(0, 8))
        self._grid_widget_label.bind("<Button-1>",
            lambda e: self._quick_toggle_custom_grid())
        self._grid_widget_label.bind("<Button-3>",
            lambda e: self._show_grid_settings())
```

The `_quick_toggle_custom_grid` method was already added to `file_ops.py` in Task 3.

- [ ] **Step 2: Manual smoke test**

Run: `python main.py`

1. Grid widget should appear in the top-right of the options bar showing "Grid: Off"
2. Left-click it → toggles custom grid on, widget shows "Grid: 16×16"
3. Right-click it → opens Grid Settings dialog
4. Ctrl+G toggles custom grid, Ctrl+H toggles pixel grid
5. View menu shows all three grid options

- [ ] **Step 3: Commit**

```bash
git add src/app.py
git commit -m "feat: add grid toolbar widget with click-to-toggle and right-click settings"
```

---

### Task 5: Grid Settings dialog

**Files:**
- Create: `src/ui/grid_dialog.py`

- [ ] **Step 1: Create the dialog**

Create `src/ui/grid_dialog.py`:

```python
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

        # Preview swatch
        self._preview = tk.Canvas(self, width=60, height=30, bg=BG_DEEP,
                                   highlightthickness=1, highlightbackground=ACCENT_CYAN)
        self._preview.pack(pady=4)
        self._update_preview()

        # Buttons
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
```

- [ ] **Step 2: Manually verify dialog renders**

Run: `python -c "import tkinter as tk; root=tk.Tk(); root.withdraw(); from src.grid import GridSettings; from src.ui.grid_dialog import GridSettingsDialog; d=GridSettingsDialog(root, GridSettings()); root.mainloop()"`

Expected: Dialog renders with all fields, color swatches are clickable, Apply/Cancel work.

- [ ] **Step 3: Commit**

```bash
git add src/ui/grid_dialog.py
git commit -m "feat: add GridSettingsDialog with RGBA color picker"
```

---

### Task 6: Project file persistence

**Files:**
- Modify: `src/project.py` (save/load grid settings)
- Modify: `src/file_ops.py` (pass grid settings through save/load, reset on new canvas)
- Modify: `src/app.py` (update load_project unpack at startup)
- Modify: `src/cli.py` (update load_project unpack at lines 97, 229)
- Modify: `src/scripting.py` (update load_project unpack at line 59)
- Modify: `tests/test_grid.py` (add persistence test)

- [ ] **Step 1: Write failing test for project persistence**

Add to `tests/test_grid.py`:

```python
class TestGridPersistence:
    def test_grid_settings_in_project_dict(self):
        """Grid settings should serialize to a dict matching the .retro format."""
        gs = GridSettings(custom_grid_visible=True, custom_grid_width=32)
        d = gs.to_dict()
        assert d["custom_visible"] is True
        assert d["custom_width"] == 32
        restored = GridSettings.from_dict(d)
        assert restored.custom_grid_visible is True
        assert restored.custom_grid_width == 32
```

- [ ] **Step 2: Update save_project to accept grid_settings**

In `src/project.py`, change the `save_project` signature:

```python
def save_project(filepath: str, timeline: AnimationTimeline,
                 palette: Palette, tool_settings: dict | None = None,
                 reference_image=None, grid_settings=None) -> None:
```

In the version logic (around line 145), update to set version 7 when grid settings are present:

```python
    has_ref = ref_data is not None
    has_grid = grid_settings is not None
    if has_grid:
        version = 7
    elif has_ref:
        version = 6
    elif tool_settings:
        version = 5
    elif getattr(timeline, 'color_mode', 'rgba') == 'indexed':
        version = 4
    else:
        version = 3
```

After the `if ref_data is not None:` block (around line 170), add:

```python
    if grid_settings is not None:
        project["grid"] = grid_settings
```

- [ ] **Step 3: Update load_project to return grid settings**

In `src/project.py`, change the `load_project` return type and add grid extraction at the end:

```python
def load_project(filepath: str) -> tuple[AnimationTimeline, Palette, dict, 'ReferenceImage | None', dict | None]:
```

At the end of `load_project`, before the return statement, add:

```python
    grid_data = project.get("grid", None)
```

Change the return to:

```python
    return timeline, palette, tool_settings, ref, grid_data
```

- [ ] **Step 4: Update file_ops.py save calls**

In `src/file_ops.py`, update all `save_project()` calls to pass grid settings. There are several call sites. For each one, add `grid_settings=self._grid_settings.to_dict()`:

In `_save_project` (line 36):
```python
                save_project(self._project_path, self.timeline, self.palette,
                             tool_settings=self._tool_settings.to_dict(),
                             reference_image=self._reference,
                             grid_settings=self._grid_settings.to_dict())
```

Apply the same pattern to `_save_project_as` (line 60) and all other `save_project` calls in the file.

- [ ] **Step 5: Update file_ops.py load call**

In `_open_project` (around line 113), update the `load_project` call to unpack the new return value. The `.retro` branch currently unpacks 4 values — change it to 5:

```python
                self.timeline, self.palette, tool_settings_data, loaded_ref, grid_data = load_project(path)
```

**Important:** The Aseprite and PSD import branches in `_open_project` do NOT call `load_project`, so they are unaffected. Only the `else` branch (line ~113) needs updating.

- [ ] **Step 5b: Update ALL other `load_project` callers**

In `src/app.py:103`, update the startup load:
```python
                self.timeline, self.palette, _tool_settings_data, _, _ = load_project(startup["path"])
```

In `src/cli.py:97`:
```python
            timeline, palette, _, _, _ = load_project(input_path)
```

In `src/cli.py:229`:
```python
            timeline, palette, _, _, _ = load_project(input_path)
```

In `src/scripting.py:59`:
```python
        timeline, palette, _, _, _ = _load(path)
```

- [ ] **Step 5c: Add grid reset in `_new_canvas`**

In `src/file_ops.py`, in the `_new_canvas` method (around line 137), after `self._reset_state()`, add:
```python
        from src.grid import GridSettings
        self._grid_settings = GridSettings()
        self._pixel_grid_var.set(True)
        self._custom_grid_var.set(False)
        self._update_grid_widget()
```

After that, restore grid settings:

```python
                if grid_data is not None:
                    from src.grid import GridSettings
                    self._grid_settings = GridSettings.from_dict(grid_data)
                else:
                    from src.grid import GridSettings
                    self._grid_settings = GridSettings()
                self._pixel_grid_var.set(self._grid_settings.pixel_grid_visible)
                self._custom_grid_var.set(self._grid_settings.custom_grid_visible)
                self._update_grid_widget()
```

- [ ] **Step 6: Run all tests**

Run: `python -m pytest tests/ -x -q`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/project.py src/file_ops.py src/app.py src/cli.py src/scripting.py tests/test_grid.py
git commit -m "feat: persist grid settings in .retro project files (version 7)"
```

---

### Task 7: Update README and final verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README feature list**

In `README.md`, in the feature list section, add after the animation/tilemap features:

```
**Canvas & Grid**
- Dual grid system: pixel grid (1×1) + custom grid (N×M) with offset
- Independent visibility toggle, RGBA color, and zoom threshold per grid
- Grid Settings dialog (Ctrl+Shift+G), toolbar widget, keyboard shortcuts (Ctrl+G, Ctrl+H)
- Grid settings persist per-project in `.retro` files
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Manual smoke test**

1. Launch `python main.py`
2. Verify pixel grid shows at zoom >= 4 (default behavior preserved)
3. Ctrl+G → custom grid appears (16×16 cyan lines)
4. Ctrl+Shift+G → Grid Settings dialog opens
5. Change custom grid to 8×8, change color to magenta, Apply
6. Grid updates immediately
7. Save project, reopen → grid settings restored
8. Ctrl+H → pixel grid toggles off/on

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add grid system features to README"
```
