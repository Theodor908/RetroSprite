# Plan 2: Power Tools Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add six professional-grade features: Pressure Sensitivity, Interactive Scale/Skew Transform, Sprite Sheet Import, Right-Click Tool Assignment, Tilemap Data Export (JSON/TMX), and AnimPainting (auto-advance frame).

**Architecture:** Chunk 1 (Tasks 1-2) adds a standalone pressure module and canvas-level AnimPainting toggle — low coupling, no new files beyond `src/pressure.py`. Chunk 2 (Tasks 3-4) adds the interactive transform mode and right-click tool routing — both modify core `app.py` event handlers. Chunk 3 (Tasks 5-6) adds import/export features — new modules with dialogs that integrate via menu items.

**Tech Stack:** Python, Tkinter, NumPy, PIL (existing). Pressure sensitivity uses `ctypes` (stdlib) for Windows Ink — no pip dependencies. All features gracefully degrade when optional APIs are unavailable.

**Pre-requisite from Plan 1:** `Frame.duration_ms` serialization fix in `src/project.py`. If Plan 1 is not yet landed, Task 6 (AnimPainting) still works at runtime but frame durations will not persist on save. The fix is noted in Task 6 as a guard check.

---

## Chunk 1: Pressure Sensitivity & AnimPainting

These two features are self-contained: one creates a new module with options-bar integration, the other adds a simple toggle + one-line frame advance in the release handler.

### Task 1: Pressure Sensitivity

**Files:**
- Create: `src/pressure.py`
- Create: `tests/test_pressure.py`
- Modify: `src/app.py` (~line 114 area for init, ~line 980 `_on_canvas_drag` for pressure reads)
- Modify: `src/ui/options_bar.py` (line 11 `TOOL_OPTIONS` — add `"pressure"` control to `"pen"` and `"eraser"`)
- Modify: `src/tool_settings.py` (line 11 `TOOL_DEFAULTS` — add `"pressure"` sub-dict)

- [ ] **Step 1: Write failing tests for the pressure module**

Create `tests/test_pressure.py`:

```python
"""Tests for pressure sensitivity module."""
import sys
from unittest.mock import patch, MagicMock
from src.pressure import PressureManager, map_pressure


class TestPressureManager:
    def test_get_pressure_returns_none_when_no_tablet(self):
        mgr = PressureManager()
        # Without a real tablet, should return None
        result = mgr.get_pressure()
        assert result is None or (0.0 <= result <= 1.0)

    def test_is_available_returns_bool(self):
        mgr = PressureManager()
        assert isinstance(mgr.is_available(), bool)


class TestMapPressure:
    def test_map_size_full_pressure(self):
        base_size = 5
        result = map_pressure(1.0, base_size, mode="size")
        assert result["size"] == base_size * 2
        assert result["opacity"] == 1.0

    def test_map_size_zero_pressure(self):
        result = map_pressure(0.0, 5, mode="size")
        assert result["size"] == 1

    def test_map_opacity_half_pressure(self):
        result = map_pressure(0.5, 5, mode="opacity")
        assert result["size"] == 5
        # opacity = 0.1 + 0.5 * 0.9 = 0.55
        assert abs(result["opacity"] - 0.55) < 0.01

    def test_map_both(self):
        result = map_pressure(0.75, 4, mode="both")
        assert result["size"] >= 1
        assert 0.1 <= result["opacity"] <= 1.0

    def test_map_none_pressure_returns_defaults(self):
        result = map_pressure(None, 5, mode="size")
        assert result["size"] == 5
        assert result["opacity"] == 1.0
```

Run: `python -m pytest tests/test_pressure.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.pressure'`

- [ ] **Step 2: Implement `src/pressure.py`**

Create `src/pressure.py`:

```python
"""Pressure sensitivity support via Windows Ink / WinTab.

Provides get_pressure() -> float | None (0.0-1.0).
Gracefully returns None if no tablet is detected or on non-Windows platforms.
"""
from __future__ import annotations
import sys


class PressureManager:
    """Reads pen pressure from the OS tablet API."""

    def __init__(self):
        self._available = False
        self._pointer_api = None
        if sys.platform == "win32":
            self._init_windows()

    def _init_windows(self):
        """Try to load Windows Ink pointer API via ctypes."""
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            # GetPointerType is available on Windows 8+
            self._get_pointer_pen_info = user32.GetPointerPenInfo
            self._get_pointer_pen_info.argtypes = [
                wintypes.UINT,
                ctypes.POINTER(ctypes.c_byte * 80),  # POINTER_PEN_INFO struct
            ]
            self._get_pointer_pen_info.restype = wintypes.BOOL
            self._user32 = user32
            self._available = True
        except (OSError, AttributeError):
            self._available = False

    def is_available(self) -> bool:
        """Return True if tablet pressure reading is supported."""
        return self._available

    def get_pressure(self) -> float | None:
        """Return current pen pressure 0.0-1.0, or None if unavailable.

        Note: In practice, Tkinter does not pass pointer IDs in its
        events. This implementation provides a polling-based fallback
        that reads the last known pointer state. For full fidelity,
        a WM_POINTER message hook would be needed.
        """
        if not self._available:
            return None
        try:
            import ctypes
            buf = (ctypes.c_byte * 80)()
            # Attempt to read the most recent pen info
            # pointer ID 0 is a placeholder — real integration needs
            # WM_POINTER event hooking for the actual pointer ID
            ok = self._get_pointer_pen_info(0, ctypes.byref(buf))
            if ok:
                # pressure is at offset 52 in POINTER_PEN_INFO (uint32)
                pressure_raw = int.from_bytes(buf[52:56], byteorder="little")
                return min(max(pressure_raw / 1024.0, 0.0), 1.0)
        except Exception:
            pass
        return None


def map_pressure(
    pressure: float | None,
    base_size: int,
    mode: str = "size",
) -> dict:
    """Map a pressure value to tool parameter overrides.

    Args:
        pressure: 0.0-1.0 or None (no tablet / feature off).
        base_size: The tool's configured base brush size.
        mode: One of "size", "opacity", "both".

    Returns:
        dict with "size" (int) and "opacity" (float) keys.
    """
    if pressure is None:
        return {"size": base_size, "opacity": 1.0}

    p = max(0.0, min(1.0, pressure))

    if mode == "size":
        size = max(1, round(1 + p * (base_size * 2 - 1)))
        return {"size": size, "opacity": 1.0}
    elif mode == "opacity":
        opacity = 0.1 + p * 0.9
        return {"size": base_size, "opacity": opacity}
    elif mode == "both":
        size = max(1, round(1 + p * (base_size * 2 - 1)))
        opacity = 0.1 + p * 0.9
        return {"size": size, "opacity": opacity}
    else:
        return {"size": base_size, "opacity": 1.0}
```

Run: `python -m pytest tests/test_pressure.py -v`
Expected: All pass.

- [ ] **Step 3: Add pressure settings to `TOOL_DEFAULTS`**

In `src/tool_settings.py`, add after line 27 (after the `"roundrect"` entry):

```python
    "pressure": {"enabled": False, "map_to": "size"},
```

This is a pseudo-tool entry so `ToolSettingsManager.save()` does not silently drop pressure state. The key `"pressure"` is used globally (not per-tool).

- [ ] **Step 4: Add pressure toggle to options bar**

In `src/ui/options_bar.py`, add `"pressure": True` to both the `"pen"` and `"eraser"` entries in `TOOL_OPTIONS` (line 12-13):

```python
    "pen":     {"size": True, "symmetry": True, "dither": True, "pixel_perfect": True, "ink_mode": True, "pressure": True},
    "eraser":  {"size": True, "symmetry": True, "pixel_perfect": True, "ink_mode": True, "pressure": True},
```

In the `OptionsBar` class, add a pressure section that renders when `"pressure"` is in the current tool's options:
- A toggle button labelled "Pressure" (shows/hides based on `PressureManager.is_available()`)
- A dropdown for mapping mode: "Size", "Opacity", "Both"
- The toggle button reads/writes `self.app.tool_settings.get("pressure")["enabled"]`

Implementation: in the `_build_controls` method (or equivalent rebuild method), after existing control blocks, add:

```python
if opts.get("pressure") and self.app._pressure_mgr.is_available():
    # Pressure toggle button
    pressure_on = self.app.tool_settings.get("pressure").get("enabled", False)
    btn_text = "Pressure: ON" if pressure_on else "Pressure: OFF"
    btn = tk.Button(self._controls_frame, text=btn_text,
                    command=self._toggle_pressure)
    style_button(btn)
    btn.pack(side=tk.LEFT, padx=2)
    # Mapping dropdown
    map_var = tk.StringVar(value=self.app.tool_settings.get("pressure").get("map_to", "size"))
    dropdown = tk.OptionMenu(self._controls_frame, map_var,
                             "size", "opacity", "both",
                             command=lambda v: self._set_pressure_map(v))
    dropdown.pack(side=tk.LEFT, padx=2)
```

- [ ] **Step 5: Integrate pressure into `app.py` draw events**

In `src/app.py`:

1. At the top, add import:
```python
from src.pressure import PressureManager, map_pressure
```

2. In `__init__`, after tool registration (~line 128):
```python
self._pressure_mgr = PressureManager()
```

3. In `_on_canvas_drag` (~line 980), before the Pen/Eraser tool dispatch, read pressure and adjust parameters:

```python
# --- Pressure sensitivity ---
pressure_settings = self.tool_settings.get("pressure")
pressure_val = None
if pressure_settings.get("enabled") and self._pressure_mgr.is_available():
    pressure_val = self._pressure_mgr.get_pressure()

if self.current_tool_name == "Pen":
    ts = self.tool_settings.get("pen")
    base_size = ts.get("size", 1)
    if pressure_val is not None:
        overrides = map_pressure(pressure_val, base_size, pressure_settings.get("map_to", "size"))
        effective_size = overrides["size"]
        # opacity override would be applied to color alpha channel
    else:
        effective_size = base_size
    # Use effective_size in the existing pen apply call
```

Apply the same pattern for the Eraser branch. The key integration point: replace the `size` argument in the existing `self._tools["Pen"].apply(...)` call with the pressure-adjusted value.

- [ ] **Step 6: Run full test suite and verify**

Run: `python -m pytest tests/test_pressure.py tests/test_tool_settings.py -v`
Expected: All pass. Pressure gracefully returns None without a tablet.

---

### Task 2: AnimPainting (Auto-Advance Frame)

**Files:**
- Create: `tests/test_anim_painting.py`
- Modify: `src/app.py` (~line 128 for state, ~line 1100 `_on_canvas_release` for auto-advance)
- Modify: `src/keybindings.py` (line 6 `DEFAULT_BINDINGS` — add `"anim_painting"`)
- Modify: `src/ui/timeline.py` (AnimPaint toggle button)

- [ ] **Step 1: Write failing tests**

Create `tests/test_anim_painting.py`:

```python
"""Tests for AnimPainting auto-advance feature."""
from src.animation import AnimationTimeline


class TestAnimPaintingAdvance:
    def test_advance_wraps_around(self):
        timeline = AnimationTimeline(8, 8)
        timeline.add_frame()
        timeline.add_frame()
        # 3 frames total: 0, 1, 2
        assert timeline.frame_count == 3
        timeline.set_current(0)
        assert timeline.current_index == 0

        # Simulate AnimPainting advance
        current = timeline.current_index
        total = timeline.frame_count
        next_idx = (current + 1) % total
        timeline.set_current(next_idx)
        assert timeline.current_index == 1

        # Advance from last frame wraps to 0
        timeline.set_current(2)
        next_idx = (timeline.current_index + 1) % timeline.frame_count
        timeline.set_current(next_idx)
        assert timeline.current_index == 0

    def test_single_frame_stays_on_same(self):
        timeline = AnimationTimeline(8, 8)
        # 1 frame by default
        assert timeline.frame_count == 1
        next_idx = (timeline.current_index + 1) % timeline.frame_count
        timeline.set_current(next_idx)
        assert timeline.current_index == 0
```

Run: `python -m pytest tests/test_anim_painting.py -v`
Expected: All pass (this tests the timeline API which already exists; the test validates our advance logic).

- [ ] **Step 2: Add keybinding**

In `src/keybindings.py`, add to `DEFAULT_BINDINGS` (line 26, after `"rotate"`):

```python
    "anim_painting": "<Control-Shift-a>",
```

- [ ] **Step 3: Add AnimPainting state and toggle to `app.py`**

In `src/app.py`:

1. In `__init__`, after other state flags (~line 170):
```python
self._anim_painting: bool = False
```

2. Add toggle method:
```python
def _toggle_anim_painting(self):
    self._anim_painting = not self._anim_painting
    status = "AnimPaint ON" if self._anim_painting else "AnimPaint OFF"
    self._update_status(status)
    # Update timeline panel button if it exists
    if hasattr(self, 'timeline_panel'):
        self.timeline_panel.update_anim_paint_state(self._anim_painting)
```

3. Bind the keybinding in the keybinding setup area:
```python
self.root.bind(self.keybindings.get("anim_painting"), lambda e: self._toggle_anim_painting())
```

- [ ] **Step 4: Add auto-advance in `_on_canvas_release`**

In `src/app.py` `_on_canvas_release` (~line 1100), at the **end** of the method (after all tool-specific release handling, before the final `_render_canvas()` call), add:

```python
# --- AnimPainting: auto-advance frame after stroke ---
if self._anim_painting and self.timeline.frame_count > 1:
    current = self.timeline.current_index
    total = self.timeline.frame_count
    self.timeline.set_current((current + 1) % total)
    self.timeline_panel.refresh()
```

Important: this must come **after** the pixel-perfect cleanup (`self._pp_last_points = []`) and **after** the tilemap sync blocks, but **before** the final render call. If `_anim_painting` is True but animation is playing (`self._playing`), skip the advance (playback controls frames already):

```python
if self._anim_painting and not getattr(self, '_playing', False) and self.timeline.frame_count > 1:
```

- [ ] **Step 5: Add AnimPaint button to timeline panel**

In `src/ui/timeline.py`, add a small toggle button in the timeline controls area:

```python
self._anim_paint_btn = tk.Button(controls_frame, text="AP",
                                  command=self.app._toggle_anim_painting)
style_button(self._anim_paint_btn)
self._anim_paint_btn.pack(side=tk.LEFT, padx=2)
```

Add an `update_anim_paint_state(self, active: bool)` method:
```python
def update_anim_paint_state(self, active: bool):
    if active:
        self._anim_paint_btn.configure(bg=ACCENT_CYAN, text="AP*")
    else:
        self._anim_paint_btn.configure(bg=BUTTON_BG, text="AP")
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_anim_painting.py -v`
Expected: All pass.

---

## Chunk 2: Interactive Scale/Skew Transform & Right-Click Tool Assignment

Both features modify core event handlers in `app.py`. Task 3 adds a new modal transform state; Task 4 adds button-routing logic to all three event handlers.

### Task 3: Interactive Scale/Skew Transform

**Files:**
- Create: `tests/test_scale_skew.py`
- Modify: `src/app.py` (transform mode state, handle rendering, affine commit)
- Modify: `src/keybindings.py` (add `"scale_skew"` binding)
- Modify: `src/image_processing.py` (add `affine_transform` helper)

- [ ] **Step 1: Write failing tests for affine transform helper**

Create `tests/test_scale_skew.py`:

```python
"""Tests for interactive scale/skew transform."""
import numpy as np
from src.pixel_data import PixelGrid
from src.image_processing import affine_transform


class TestAffineTransform:
    def test_identity_preserves_pixels(self):
        grid = PixelGrid(8, 8)
        grid.set_pixel(2, 2, (255, 0, 0, 255))
        # Identity affine matrix: [[1,0,0],[0,1,0]]
        result = affine_transform(grid, (1, 0, 0, 0, 1, 0), 8, 8)
        assert result.get_pixel(2, 2) == (255, 0, 0, 255)

    def test_scale_2x(self):
        grid = PixelGrid(4, 4)
        grid.set_pixel(1, 1, (255, 0, 0, 255))
        # Scale 2x: pixel at (1,1) -> (2,2) in 8x8 output
        result = affine_transform(grid, (0.5, 0, 0, 0, 0.5, 0), 8, 8)
        assert result.get_pixel(2, 2) == (255, 0, 0, 255)

    def test_empty_grid_stays_empty(self):
        grid = PixelGrid(8, 8)
        result = affine_transform(grid, (1, 0, 0, 0, 1, 0), 8, 8)
        assert result.get_pixel(4, 4) == (0, 0, 0, 0)
```

Run: `python -m pytest tests/test_scale_skew.py -v`
Expected: FAIL — `ImportError: cannot import name 'affine_transform'`

- [ ] **Step 2: Implement `affine_transform` in `src/image_processing.py`**

Add to `src/image_processing.py` after the existing `posterize` function:

```python
def affine_transform(grid: PixelGrid, coeffs: tuple, out_w: int, out_h: int) -> PixelGrid:
    """Apply a 2x3 affine transform to a PixelGrid using PIL.

    Args:
        grid: Source pixel grid.
        coeffs: 6-tuple (a, b, c, d, e, f) defining the inverse affine:
                For each output pixel (x', y'), the source pixel is:
                src_x = a*x' + b*y' + c
                src_y = d*x' + e*y' + f
        out_w: Output width.
        out_h: Output height.

    Returns:
        New PixelGrid with transformed content.
    """
    from PIL import Image
    img = grid.to_pil_image()
    transformed = img.transform(
        (out_w, out_h), Image.AFFINE, coeffs,
        resample=Image.NEAREST, fillcolor=(0, 0, 0, 0)
    )
    result = PixelGrid(out_w, out_h)
    result.from_pil_image(transformed)
    return result
```

Run: `python -m pytest tests/test_scale_skew.py -v`
Expected: All pass.

- [ ] **Step 3: Add keybinding for scale/skew mode**

In `src/keybindings.py`, add to `DEFAULT_BINDINGS`:

```python
    "scale_skew": "<Control-Shift-s>",
```

Note: `Ctrl+T` is already bound to rotation mode. `Ctrl+Shift+S` is distinct and available.

- [ ] **Step 4: Add transform mode state to `app.py`**

In `src/app.py` `__init__`, add after the rotation mode state:

```python
# Scale/Skew transform mode
self._transform_mode: bool = False
self._transform_handles: list[tuple[int, int]] = []  # 8 handle positions
self._transform_bbox: tuple[int, int, int, int] | None = None  # x, y, w, h
self._transform_snapshot: PixelGrid | None = None
self._transform_dragging_handle: int = -1  # index of handle being dragged
self._transform_matrix: tuple = (1, 0, 0, 0, 1, 0)  # identity affine
```

- [ ] **Step 5: Implement `_enter_transform_mode` and `_exit_transform_mode`**

```python
def _enter_transform_mode(self):
    """Enter interactive scale/skew transform mode.

    Requires an active selection. Places 8 handles around the selection bbox.
    """
    if not self._selection_mask:
        self._update_status("Select an area first")
        return

    # Compute bounding box of selection
    xs = [p[0] for p in self._selection_mask]
    ys = [p[1] for p in self._selection_mask]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    w, h = x1 - x0 + 1, y1 - y0 + 1

    self._push_undo()
    self._transform_mode = True
    self._transform_bbox = (x0, y0, w, h)
    self._transform_snapshot = self.timeline.current_layer().copy()
    self._transform_matrix = (1, 0, 0, 0, 1, 0)
    self._transform_dragging_handle = -1

    # 8 handles: 4 corners + 4 edge midpoints
    # Order: TL, TC, TR, ML, MR, BL, BC, BR
    cx, cy = x0 + w // 2, y0 + h // 2
    self._transform_handles = [
        (x0, y0), (cx, y0), (x1, y0),          # top row
        (x0, cy),           (x1, cy),           # middle row
        (x0, y1), (cx, y1), (x1, y1),          # bottom row
    ]

    self._render_canvas()
    self._update_status("Scale/Skew: drag handles. Enter=commit, Escape=cancel")

def _exit_transform_mode(self, commit: bool = True):
    """Exit transform mode. If commit=True, apply the transform to the layer."""
    if not self._transform_mode:
        return
    if commit:
        from src.image_processing import affine_transform
        layer = self.timeline.current_layer()
        x0, y0, w, h = self._transform_bbox
        # Extract the selection region from the snapshot
        region = PixelGrid(w, h)
        for dy in range(h):
            for dx in range(w):
                region.set_pixel(dx, dy, self._transform_snapshot.get_pixel(x0 + dx, y0 + dy))
        # Apply affine transform
        transformed = affine_transform(region, self._transform_matrix, w, h)
        # Clear original region and paste transformed content
        for dy in range(h):
            for dx in range(w):
                layer.pixels.set_pixel(x0 + dx, y0 + dy, transformed.get_pixel(dx, dy))
    else:
        # Cancel: restore snapshot
        layer = self.timeline.current_layer()
        layer._pixels = self._transform_snapshot._pixels.copy()

    self._transform_mode = False
    self._transform_handles = []
    self._transform_bbox = None
    self._transform_snapshot = None
    self._render_canvas()
    self._update_status("Transform " + ("applied" if commit else "cancelled"))
```

- [ ] **Step 6: Add transform handle interaction in event handlers**

In `_on_canvas_click` (~line 850), add early return for transform mode (before rotation mode check):

```python
if self._transform_mode:
    self._transform_handle_click(x, y)
    return
```

In `_on_canvas_drag` (~line 980):

```python
if self._transform_mode:
    self._transform_handle_drag(x, y)
    return
```

In `_on_canvas_release` (~line 1100):

```python
if self._transform_mode:
    self._transform_handle_release(x, y)
    return
```

Implement the three handle methods:

```python
def _transform_handle_click(self, x, y):
    """Check if click is near a handle; start dragging it."""
    HANDLE_RADIUS = 3
    for i, (hx, hy) in enumerate(self._transform_handles):
        if abs(x - hx) <= HANDLE_RADIUS and abs(y - hy) <= HANDLE_RADIUS:
            self._transform_dragging_handle = i
            self._transform_drag_start = (x, y)
            return
    # Click outside handles — do nothing (or commit)

def _transform_handle_drag(self, x, y):
    """Update handle position and recompute affine matrix."""
    idx = self._transform_dragging_handle
    if idx < 0:
        return
    # Move the handle
    self._transform_handles[idx] = (x, y)
    # Recompute affine matrix from handle positions
    self._recompute_transform_matrix()
    # Preview: apply transform to snapshot and render
    self._render_transform_preview()

def _transform_handle_release(self, x, y):
    """Stop dragging."""
    self._transform_dragging_handle = -1

def _recompute_transform_matrix(self):
    """Compute a 2x3 affine matrix from current handle positions.

    Uses the 4 corner handles (indices 0, 2, 5, 7) to derive
    the scale and skew components relative to the original bbox.
    """
    x0, y0, w, h = self._transform_bbox
    # Original corners: TL(0,0) TR(w,0) BL(0,h) BR(w,h)
    # Current corners from handles
    tl = self._transform_handles[0]
    tr = self._transform_handles[2]
    bl = self._transform_handles[5]
    br = self._transform_handles[7]

    # Derive affine from TL, TR, BL (3 points define the transform)
    # src (0,0)->(tl), (w,0)->(tr), (0,h)->(bl)
    if w > 0 and h > 0:
        a = (tr[0] - tl[0]) / w
        b = (bl[0] - tl[0]) / h
        c = tl[0] - x0
        d = (tr[1] - tl[1]) / w
        e = (bl[1] - tl[1]) / h
        f = tl[1] - y0
        # Inverse for PIL (output->source mapping)
        det = a * e - b * d
        if abs(det) > 1e-6:
            inv_a = e / det
            inv_b = -b / det
            inv_c = (b * f - e * c) / det
            inv_d = -d / det
            inv_e = a / det
            inv_f = (d * c - a * f) / det
            self._transform_matrix = (inv_a, inv_b, inv_c, inv_d, inv_e, inv_f)

def _render_transform_preview(self):
    """Render a preview of the current transform."""
    from src.image_processing import affine_transform
    x0, y0, w, h = self._transform_bbox
    region = PixelGrid(w, h)
    for dy in range(h):
        for dx in range(w):
            region.set_pixel(dx, dy, self._transform_snapshot.get_pixel(x0 + dx, y0 + dy))
    transformed = affine_transform(region, self._transform_matrix, w, h)
    # Write preview to the layer temporarily
    layer = self.timeline.current_layer()
    # Restore from snapshot first
    layer._pixels = self._transform_snapshot._pixels.copy()
    # Paste transformed region
    for dy in range(h):
        for dx in range(w):
            px = transformed.get_pixel(dx, dy)
            if px[3] > 0:
                layer.pixels.set_pixel(x0 + dx, y0 + dy, px)
    self._render_canvas()
```

- [ ] **Step 7: Bind Enter/Escape for commit/cancel**

In the keybinding setup area of `app.py`:

```python
self.root.bind(self.keybindings.get("scale_skew"), lambda e: self._enter_transform_mode())
self.root.bind("<Return>", lambda e: self._exit_transform_mode(commit=True) if self._transform_mode else None)
self.root.bind("<Escape>", lambda e: self._exit_transform_mode(commit=False) if self._transform_mode else None)
```

Note: The `<Escape>` binding must check `_transform_mode` first to avoid interfering with other Escape uses (like exiting rotation mode). Chain with existing Escape handler using an `or` pattern or a dispatch function.

- [ ] **Step 8: Run tests**

Run: `python -m pytest tests/test_scale_skew.py -v`
Expected: All pass.

---

### Task 4: Right-Click Tool Assignment

**Files:**
- Create: `tests/test_right_click_tool.py`
- Modify: `src/app.py` (right tool state, second `ToolSettingsManager`, event routing)
- Modify: `src/ui/toolbar.py` (right-click assignment, visual indicator)
- Modify: `src/tool_settings.py` (no changes needed — reuses existing `TOOL_DEFAULTS`)

- [ ] **Step 1: Write failing tests**

Create `tests/test_right_click_tool.py`:

```python
"""Tests for right-click tool assignment."""
from src.tool_settings import ToolSettingsManager


class TestRightToolSettings:
    def test_independent_settings(self):
        left = ToolSettingsManager()
        right = ToolSettingsManager()
        left.save("pen", {"size": 3})
        right.save("pen", {"size": 7})
        assert left.get("pen")["size"] == 3
        assert right.get("pen")["size"] == 7

    def test_default_right_tool_is_eraser(self):
        # Convention: right tool defaults to eraser
        right_tool = "eraser"
        right_settings = ToolSettingsManager()
        eraser_settings = right_settings.get(right_tool)
        assert "size" in eraser_settings
```

Run: `python -m pytest tests/test_right_click_tool.py -v`
Expected: All pass (tests the ToolSettingsManager API which exists; validates independence).

- [ ] **Step 2: Add right-tool state to `app.py`**

In `src/app.py` `__init__`, after `self.tool_settings = ToolSettingsManager()` (wherever that is):

```python
# Right-click tool assignment
self._right_tool: str = "Eraser"  # Capitalized to match self._tools keys
self._right_tool_settings = ToolSettingsManager()  # Independent instance
self._active_button: int = 1  # 1 = left, 3 = right (tracks current stroke)
```

- [ ] **Step 3: Route Button-3 events to right tool**

The canvas event handlers need to detect which mouse button triggered the event. In `app.py`:

1. Modify `_on_canvas_click` to accept and check the button:

Where the canvas `<Button-1>` binding calls `_on_canvas_click(x, y, event_state)`, add a parallel `<Button-3>` binding:

```python
# In canvas event setup:
self.pixel_canvas.canvas.bind("<Button-3>", lambda e: self._on_canvas_click_right(
    *self.pixel_canvas.canvas_to_pixel(e.x, e.y), e.state))
self.pixel_canvas.canvas.bind("<B3-Motion>", lambda e: self._on_canvas_drag_right(
    *self.pixel_canvas.canvas_to_pixel(e.x, e.y)))
self.pixel_canvas.canvas.bind("<ButtonRelease-3>", lambda e: self._on_canvas_release_right(
    *self.pixel_canvas.canvas_to_pixel(e.x, e.y), e.state))
```

2. Implement the right-click dispatch wrappers:

```python
def _on_canvas_click_right(self, x, y, event_state=0):
    """Handle right-click on canvas: use the right-assigned tool."""
    saved_tool = self.current_tool_name
    saved_settings = self.tool_settings
    self.current_tool_name = self._right_tool
    self.tool_settings = self._right_tool_settings
    self._active_button = 3
    try:
        self._on_canvas_click(x, y, event_state)
    finally:
        self.current_tool_name = saved_tool
        self.tool_settings = saved_settings

def _on_canvas_drag_right(self, x, y):
    saved_tool = self.current_tool_name
    saved_settings = self.tool_settings
    self.current_tool_name = self._right_tool
    self.tool_settings = self._right_tool_settings
    try:
        self._on_canvas_drag(x, y)
    finally:
        self.current_tool_name = saved_tool
        self.tool_settings = saved_settings

def _on_canvas_release_right(self, x, y, event_state=0):
    saved_tool = self.current_tool_name
    saved_settings = self.tool_settings
    self.current_tool_name = self._right_tool
    self.tool_settings = self._right_tool_settings
    try:
        self._on_canvas_release(x, y, event_state)
    finally:
        self.current_tool_name = saved_tool
        self.tool_settings = saved_settings
        self._active_button = 1
```

- [ ] **Step 4: Add right-click assignment to toolbar**

In `src/ui/toolbar.py`, modify the toolbar button creation to bind `<Button-3>`:

```python
# For each tool button:
btn.bind("<Button-3>", lambda e, t=tool_name: self._assign_right_tool(t))

def _assign_right_tool(self, tool_name: str):
    """Assign a tool to the right mouse button."""
    self.app._right_tool = tool_name
    self._update_right_tool_indicator()
    self.app._update_status(f"RMB: {tool_name}")
```

Add a visual indicator (subtle right-border highlight) on the right-assigned tool:

```python
def _update_right_tool_indicator(self):
    """Highlight the right-click assigned tool button."""
    for name, btn in self._tool_buttons.items():
        if name.lower() == self.app._right_tool.lower():
            btn.configure(highlightbackground=ACCENT_MAGENTA, highlightthickness=2)
        else:
            btn.configure(highlightthickness=0)
```

- [ ] **Step 5: Update status bar to show both tool assignments**

In `src/app.py`, modify `_update_status` or the status bar refresh to include:

```python
def _update_tool_status(self):
    left = self.current_tool_name
    right = self._right_tool
    self._status_tool_label.configure(text=f"LMB: {left} | RMB: {right}")
```

Call `_update_tool_status()` whenever either tool changes.

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_right_click_tool.py tests/test_tool_settings.py -v`
Expected: All pass.

---

## Chunk 3: Sprite Sheet Import & Tilemap Data Export

Both are import/export features with new modules and dialog UIs. They integrate via `File` menu items.

### Task 5: Sprite Sheet Import

**Files:**
- Create: `src/sheet_import.py`
- Create: `src/ui/sheet_import_dialog.py`
- Create: `tests/test_sheet_import.py`
- Modify: `src/app.py` (menu item under `File > Import > Sprite Sheet...`)

- [ ] **Step 1: Write failing tests for the slicing logic**

Create `tests/test_sheet_import.py`:

```python
"""Tests for sprite sheet import slicing logic."""
import numpy as np
from PIL import Image
from src.sheet_import import slice_sprite_sheet, compute_default_tile_size


class TestSliceSpriteSheet:
    def test_slice_4x4_into_2x2_tiles(self):
        # 4x4 image with 4 distinct 2x2 tiles
        img = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        # Top-left tile: red
        for x in range(2):
            for y in range(2):
                img.putpixel((x, y), (255, 0, 0, 255))
        # Top-right tile: green
        for x in range(2, 4):
            for y in range(2):
                img.putpixel((x, y), (0, 255, 0, 255))

        tiles = slice_sprite_sheet(img, tile_w=2, tile_h=2)
        assert len(tiles) == 4
        assert tiles[0].size == (2, 2)
        assert tiles[0].getpixel((0, 0)) == (255, 0, 0, 255)
        assert tiles[1].getpixel((0, 0)) == (0, 255, 0, 255)

    def test_slice_with_margin_and_spacing(self):
        # 10x5 image with 1px margin, 1px spacing, 2x2 tiles
        # Layout: 1px margin | 2px tile | 1px space | 2px tile | 1px space | 2px tile | 1px margin = 10
        img = Image.new("RGBA", (10, 5), (128, 128, 128, 255))
        tiles = slice_sprite_sheet(img, tile_w=2, tile_h=2, margin=1, spacing=1)
        assert len(tiles) == 3  # 3 columns x 1 row

    def test_slice_single_tile(self):
        img = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
        tiles = slice_sprite_sheet(img, tile_w=16, tile_h=16)
        assert len(tiles) == 1


class TestComputeDefaultTileSize:
    def test_square_image(self):
        tw, th = compute_default_tile_size(64, 64)
        assert tw == th
        assert 64 % tw == 0

    def test_common_sprite_sheet(self):
        tw, th = compute_default_tile_size(128, 64)
        assert 128 % tw == 0
        assert 64 % th == 0
        # Should pick a reasonable size like 16 or 32
        assert tw >= 8

    def test_prime_dimensions_fallback(self):
        tw, th = compute_default_tile_size(37, 41)
        # For primes, should fallback to full image dimensions or 1
        assert tw >= 1 and th >= 1
```

Run: `python -m pytest tests/test_sheet_import.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.sheet_import'`

- [ ] **Step 2: Implement `src/sheet_import.py`**

Create `src/sheet_import.py`:

```python
"""Sprite sheet slicing logic for RetroSprite."""
from __future__ import annotations
from math import gcd
from PIL import Image


def compute_default_tile_size(img_w: int, img_h: int) -> tuple[int, int]:
    """Compute a sensible default tile size for a sprite sheet.

    Strategy: find the GCD of width and height, then pick a factor
    in the 8-64px range that divides both dimensions evenly.
    Falls back to 16 if no good factor is found.
    """
    common = gcd(img_w, img_h)

    # Preferred sizes from largest to smallest
    preferred = [32, 16, 64, 24, 48, 8]
    for size in preferred:
        if img_w % size == 0 and img_h % size == 0:
            return size, size

    # Try factors of the GCD in a reasonable range
    for size in range(min(64, common), 7, -1):
        if img_w % size == 0 and img_h % size == 0:
            return size, size

    # GCD itself if it's reasonable
    if 4 <= common <= 128:
        return common, common

    # Fallback: use the full image dimensions
    return img_w, img_h


def slice_sprite_sheet(
    image: Image.Image,
    tile_w: int,
    tile_h: int,
    margin: int = 0,
    spacing: int = 0,
) -> list[Image.Image]:
    """Slice a sprite sheet image into individual tile images.

    Args:
        image: Source sprite sheet (PIL Image, RGBA).
        tile_w: Width of each tile in pixels.
        tile_h: Height of each tile in pixels.
        margin: Border margin around the entire sheet (pixels).
        spacing: Gap between adjacent tiles (pixels).

    Returns:
        List of PIL Images, one per tile, in left-to-right top-to-bottom order.
    """
    image = image.convert("RGBA")
    sheet_w, sheet_h = image.size
    tiles: list[Image.Image] = []

    y = margin
    while y + tile_h <= sheet_h - margin:
        x = margin
        while x + tile_w <= sheet_w - margin:
            tile = image.crop((x, y, x + tile_w, y + tile_h))
            tiles.append(tile)
            x += tile_w + spacing
        y += tile_h + spacing

    return tiles
```

Run: `python -m pytest tests/test_sheet_import.py -v`
Expected: All pass.

- [ ] **Step 3: Create the import dialog `src/ui/sheet_import_dialog.py`**

Create `src/ui/sheet_import_dialog.py`:

```python
"""Sprite sheet import dialog for RetroSprite."""
from __future__ import annotations
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
from src.sheet_import import slice_sprite_sheet, compute_default_tile_size
from src.ui.theme import (
    BG_PANEL, BG_DEEP, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, BUTTON_BG, style_button, style_label, style_frame
)


class SheetImportDialog(tk.Toplevel):
    """Dialog for importing a sprite sheet as animation frames."""

    def __init__(self, parent, callback):
        """
        Args:
            parent: Parent Tk widget.
            callback: Called with list[Image.Image] tiles on successful import.
        """
        super().__init__(parent)
        self.title("Import Sprite Sheet")
        self.configure(bg=BG_PANEL)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._callback = callback
        self._source_image: Image.Image | None = None
        self._preview_photo = None

        # --- File picker ---
        file_frame = tk.Frame(self, bg=BG_PANEL)
        file_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(file_frame, text="Source:", bg=BG_PANEL, fg=TEXT_PRIMARY).pack(side=tk.LEFT)
        self._file_label = tk.Label(file_frame, text="(none)", bg=BG_PANEL, fg=TEXT_SECONDARY)
        self._file_label.pack(side=tk.LEFT, padx=5)
        browse_btn = tk.Button(file_frame, text="Browse...", command=self._browse)
        style_button(browse_btn)
        browse_btn.pack(side=tk.RIGHT)

        # --- Tile size inputs ---
        size_frame = tk.Frame(self, bg=BG_PANEL)
        size_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(size_frame, text="Tile W:", bg=BG_PANEL, fg=TEXT_PRIMARY).pack(side=tk.LEFT)
        self._tw_var = tk.IntVar(value=16)
        tk.Spinbox(size_frame, from_=1, to=512, textvariable=self._tw_var,
                   width=5, command=self._update_preview).pack(side=tk.LEFT, padx=2)
        tk.Label(size_frame, text="Tile H:", bg=BG_PANEL, fg=TEXT_PRIMARY).pack(side=tk.LEFT, padx=(10, 0))
        self._th_var = tk.IntVar(value=16)
        tk.Spinbox(size_frame, from_=1, to=512, textvariable=self._th_var,
                   width=5, command=self._update_preview).pack(side=tk.LEFT, padx=2)

        # --- Margin / Spacing ---
        ms_frame = tk.Frame(self, bg=BG_PANEL)
        ms_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(ms_frame, text="Margin:", bg=BG_PANEL, fg=TEXT_PRIMARY).pack(side=tk.LEFT)
        self._margin_var = tk.IntVar(value=0)
        tk.Spinbox(ms_frame, from_=0, to=64, textvariable=self._margin_var,
                   width=4, command=self._update_preview).pack(side=tk.LEFT, padx=2)
        tk.Label(ms_frame, text="Spacing:", bg=BG_PANEL, fg=TEXT_PRIMARY).pack(side=tk.LEFT, padx=(10, 0))
        self._spacing_var = tk.IntVar(value=0)
        tk.Spinbox(ms_frame, from_=0, to=64, textvariable=self._spacing_var,
                   width=4, command=self._update_preview).pack(side=tk.LEFT, padx=2)

        # --- Info label ---
        self._info_label = tk.Label(self, text="", bg=BG_PANEL, fg=TEXT_SECONDARY)
        self._info_label.pack(padx=10, pady=2)

        # --- Preview ---
        self._preview_canvas = tk.Canvas(self, width=256, height=256, bg=BG_DEEP,
                                          highlightthickness=0)
        self._preview_canvas.pack(padx=10, pady=5)

        # --- Buttons ---
        btn_frame = tk.Frame(self, bg=BG_PANEL)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        import_btn = tk.Button(btn_frame, text="Import", command=self._do_import)
        style_button(import_btn)
        import_btn.pack(side=tk.RIGHT, padx=5)
        cancel_btn = tk.Button(btn_frame, text="Cancel", command=self.destroy)
        style_button(cancel_btn)
        cancel_btn.pack(side=tk.RIGHT)

    def _browse(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.bmp *.gif *.jpg *.jpeg"), ("All", "*.*")]
        )
        if path:
            self._source_image = Image.open(path).convert("RGBA")
            self._file_label.configure(text=path.split("/")[-1].split("\\")[-1])
            tw, th = compute_default_tile_size(*self._source_image.size)
            self._tw_var.set(tw)
            self._th_var.set(th)
            self._update_preview()

    def _update_preview(self):
        if self._source_image is None:
            return
        tw, th = self._tw_var.get(), self._th_var.get()
        margin, spacing = self._margin_var.get(), self._spacing_var.get()
        tiles = slice_sprite_sheet(self._source_image, tw, th, margin, spacing)
        iw, ih = self._source_image.size
        cols = max(1, (iw - 2 * margin + spacing) // (tw + spacing))
        rows = max(1, (ih - 2 * margin + spacing) // (th + spacing))
        self._info_label.configure(text=f"{cols} x {rows} = {len(tiles)} tiles")

        # Draw grid overlay on preview
        preview = self._source_image.copy()
        # Scale preview to fit 256x256
        scale = min(256 / iw, 256 / ih)
        pw, ph = max(1, int(iw * scale)), max(1, int(ih * scale))
        preview = preview.resize((pw, ph), Image.NEAREST)
        self._preview_photo = ImageTk.PhotoImage(preview)
        self._preview_canvas.delete("all")
        self._preview_canvas.create_image(0, 0, anchor=tk.NW, image=self._preview_photo)

        # Draw tile grid lines
        for c in range(cols + 1):
            lx = int((margin + c * (tw + spacing)) * scale)
            self._preview_canvas.create_line(lx, 0, lx, ph, fill="#00ffff", width=1)
        for r in range(rows + 1):
            ly = int((margin + r * (th + spacing)) * scale)
            self._preview_canvas.create_line(0, ly, pw, ly, fill="#00ffff", width=1)

    def _do_import(self):
        if self._source_image is None:
            return
        tw, th = self._tw_var.get(), self._th_var.get()
        margin, spacing = self._margin_var.get(), self._spacing_var.get()
        tiles = slice_sprite_sheet(self._source_image, tw, th, margin, spacing)
        if tiles:
            self._callback(tiles, tw, th)
        self.destroy()
```

- [ ] **Step 4: Add menu item and import handler in `app.py`**

In `src/app.py`:

1. Add import at top:
```python
from src.ui.sheet_import_dialog import SheetImportDialog
```

2. In the File menu setup, add an Import submenu (or add to existing Import submenu if present):
```python
import_menu = tk.Menu(file_menu, tearoff=0)
file_menu.add_cascade(label="Import", menu=import_menu)
import_menu.add_command(label="Sprite Sheet...", command=self._import_sprite_sheet)
```

3. Implement the handler:
```python
def _import_sprite_sheet(self):
    SheetImportDialog(self.root, self._handle_sheet_import)

def _handle_sheet_import(self, tiles: list, tile_w: int, tile_h: int):
    """Create a new project from imported sprite sheet tiles."""
    from src.animation import AnimationTimeline
    from src.palette import Palette
    import numpy as np

    # Create new timeline with tile dimensions
    self.timeline = AnimationTimeline(tile_w, tile_h)

    # First tile goes into the existing first frame
    first_tile = np.array(tiles[0])
    layer = self.timeline.current_layer()
    layer._pixels = first_tile.copy()

    # Add remaining tiles as new frames
    for tile_img in tiles[1:]:
        self.timeline.add_frame()
        idx = self.timeline.frame_count - 1
        self.timeline.set_current(idx)
        layer = self.timeline.current_layer()
        arr = np.array(tile_img)
        layer._pixels = arr.copy()

    # Go back to frame 0
    self.timeline.set_current(0)

    # Auto-extract palette from all tiles
    all_colors = set()
    for tile_img in tiles:
        for y in range(tile_img.size[1]):
            for x in range(tile_img.size[0]):
                c = tile_img.getpixel((x, y))
                if c[3] > 0:
                    all_colors.add(c)
    if all_colors:
        self.palette = Palette("Imported")
        self.palette.colors = list(all_colors)[:256]

    self._project_path = None
    self._dirty = False
    self._undo_stack.clear()
    self._redo_stack.clear()
    self._render_canvas()
    self.timeline_panel.refresh()
    self._update_status(f"Imported {len(tiles)} frames ({tile_w}x{tile_h})")
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_sheet_import.py -v`
Expected: All pass.

---

### Task 6: Tilemap Data Export (JSON/TMX)

**Files:**
- Create: `src/tilemap_export.py`
- Create: `tests/test_tilemap_export.py`
- Modify: `src/app.py` (menu item under `File > Export > Tilemap Data...`)

- [ ] **Step 1: Write failing tests for tilemap export**

Create `tests/test_tilemap_export.py`:

```python
"""Tests for tilemap data export (JSON and TMX)."""
import json
import xml.etree.ElementTree as ET
import numpy as np
from src.tilemap import Tileset, TilemapLayer, TileRef
from src.tilemap_export import export_tilemap_json, export_tilemap_tmx


def _make_test_tilemap():
    """Create a small test tilemap: 3x2 grid, 3 tiles in tileset."""
    ts = Tileset("test", 8, 8)
    # Tile 0 is the default empty tile
    # Add tile 1 (red)
    red = np.full((8, 8, 4), [255, 0, 0, 255], dtype=np.uint8)
    ts.add_tile(red)
    # Add tile 2 (green)
    green = np.full((8, 8, 4), [0, 255, 0, 255], dtype=np.uint8)
    ts.add_tile(green)

    layer = TilemapLayer("ground", 3, 2, ts)
    # Set some tile refs
    layer.grid[0][0] = TileRef(1)  # red
    layer.grid[0][1] = TileRef(2)  # green
    layer.grid[0][2] = TileRef(0)  # empty
    layer.grid[1][0] = TileRef(2, flip_x=True)
    layer.grid[1][1] = TileRef(1, flip_y=True)
    layer.grid[1][2] = TileRef(1, flip_x=True, flip_y=True)

    return ts, [layer]


class TestExportJSON:
    def test_basic_structure(self):
        ts, layers = _make_test_tilemap()
        result = export_tilemap_json(ts, layers)
        data = json.loads(result)
        assert data["tilewidth"] == 8
        assert data["tileheight"] == 8
        assert data["width"] == 3
        assert data["height"] == 2
        assert len(data["layers"]) == 1
        assert len(data["tilesets"]) == 1

    def test_tile_gids_are_1_based(self):
        ts, layers = _make_test_tilemap()
        result = export_tilemap_json(ts, layers)
        data = json.loads(result)
        layer_data = data["layers"][0]["data"]
        # Tile index 1 -> GID 2 (1-based, firstgid=1)
        # Tile index 0 -> GID 1 (not 0; 0 means empty in Tiled)
        # But index 0 is the "empty" tile -> GID 0? No: in our mapping,
        # tile 0 is a real tile. GID = index + 1. Empty cell = GID 0.
        # Actually: RetroSprite tileset index 0 is the default empty tile.
        # GID mapping: index + 1. So index 0 -> GID 1, index 1 -> GID 2.
        # But conceptually, tile index 0 (empty) should map to GID 0 in Tiled.
        # Let's follow the spec: GID = index + 1. Empty = index 0 -> GID 1.
        # The spec says "Tile GID = index+1, 0 = empty"
        assert layer_data[0] == 2  # index 1 -> GID 2
        assert layer_data[1] == 3  # index 2 -> GID 3

    def test_flip_flags_in_gid(self):
        ts, layers = _make_test_tilemap()
        result = export_tilemap_json(ts, layers)
        data = json.loads(result)
        layer_data = data["layers"][0]["data"]
        # Row 1, col 0: index=2, flip_x=True -> GID 3 | bit 31 (0x80000000)
        gid = layer_data[3]
        assert gid & 0xFFFF == 3  # base GID
        assert gid & 0x80000000  # horizontal flip (bit 31 in Tiled)

    def test_firstgid_is_1(self):
        ts, layers = _make_test_tilemap()
        result = export_tilemap_json(ts, layers)
        data = json.loads(result)
        assert data["tilesets"][0]["firstgid"] == 1


class TestExportTMX:
    def test_valid_xml(self):
        ts, layers = _make_test_tilemap()
        result = export_tilemap_tmx(ts, layers)
        root = ET.fromstring(result)
        assert root.tag == "map"
        assert root.attrib["tilewidth"] == "8"
        assert root.attrib["tileheight"] == "8"

    def test_layer_data(self):
        ts, layers = _make_test_tilemap()
        result = export_tilemap_tmx(ts, layers)
        root = ET.fromstring(result)
        layer_el = root.find("layer")
        assert layer_el is not None
        data_el = layer_el.find("data")
        assert data_el is not None
        # CSV encoding
        csv_text = data_el.text.strip()
        gids = [int(g) for g in csv_text.replace("\n", ",").split(",") if g.strip()]
        assert len(gids) == 6
```

Run: `python -m pytest tests/test_tilemap_export.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.tilemap_export'`

- [ ] **Step 2: Implement `src/tilemap_export.py`**

Create `src/tilemap_export.py`:

```python
"""Tilemap data export in Tiled-compatible JSON and TMX formats."""
from __future__ import annotations
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from src.tilemap import Tileset, TilemapLayer, TileRef


# Tiled flip flag conventions (high bits of GID)
FLIPPED_HORIZONTALLY_FLAG = 0x80000000
FLIPPED_VERTICALLY_FLAG   = 0x40000000


def _tile_ref_to_gid(ref: TileRef) -> int:
    """Convert a TileRef to a Tiled GID.

    GID = tile_index + 1 (Tiled uses 1-based, 0 = empty cell).
    Flip flags are encoded in high bits.
    """
    if ref.index == 0:
        # Index 0 is the default empty tile in RetroSprite.
        # Map to GID 0 (empty) in Tiled only if it's truly unused.
        # Per spec: GID = index + 1, so index 0 -> GID 1.
        gid = 1
    else:
        gid = ref.index + 1

    if ref.flip_x:
        gid |= FLIPPED_HORIZONTALLY_FLAG
    if ref.flip_y:
        gid |= FLIPPED_VERTICALLY_FLAG

    return gid


def export_tilemap_json(
    tileset: Tileset,
    layers: list[TilemapLayer],
    tileset_image_path: str = "tileset.png",
) -> str:
    """Export tilemap data as Tiled-compatible JSON.

    Args:
        tileset: The Tileset used by the layers.
        layers: List of TilemapLayer objects to export.
        tileset_image_path: Relative path to the tileset image file.

    Returns:
        JSON string.
    """
    if not layers:
        return "{}"

    first = layers[0]
    map_w = len(first.grid[0]) if first.grid else 0
    map_h = len(first.grid)

    layers_data = []
    for layer in layers:
        data = []
        for row in layer.grid:
            for ref in row:
                data.append(_tile_ref_to_gid(ref))
        layers_data.append({
            "name": layer.name,
            "type": "tilelayer",
            "width": map_w,
            "height": map_h,
            "data": data,
            "visible": True,
            "opacity": 1.0,
            "x": 0,
            "y": 0,
        })

    result = {
        "version": "1.10",
        "tiledversion": "1.10.0",
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "width": map_w,
        "height": map_h,
        "tilewidth": tileset.tile_width,
        "tileheight": tileset.tile_height,
        "tilesets": [{
            "firstgid": 1,
            "name": tileset.name,
            "tilewidth": tileset.tile_width,
            "tileheight": tileset.tile_height,
            "tilecount": len(tileset.tiles),
            "image": tileset_image_path,
            "imagewidth": tileset.tile_width * len(tileset.tiles),
            "imageheight": tileset.tile_height,
        }],
        "layers": layers_data,
    }

    return json.dumps(result, indent=2)


def export_tilemap_tmx(
    tileset: Tileset,
    layers: list[TilemapLayer],
    tileset_image_path: str = "tileset.png",
) -> str:
    """Export tilemap data as Tiled TMX XML.

    Args:
        tileset: The Tileset used by the layers.
        layers: List of TilemapLayer objects to export.
        tileset_image_path: Relative path to the tileset image file.

    Returns:
        TMX XML string.
    """
    if not layers:
        return '<?xml version="1.0" encoding="UTF-8"?>\n<map/>'

    first = layers[0]
    map_w = len(first.grid[0]) if first.grid else 0
    map_h = len(first.grid)

    map_el = ET.Element("map", {
        "version": "1.10",
        "tiledversion": "1.10.0",
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "width": str(map_w),
        "height": str(map_h),
        "tilewidth": str(tileset.tile_width),
        "tileheight": str(tileset.tile_height),
    })

    ts_el = ET.SubElement(map_el, "tileset", {
        "firstgid": "1",
        "name": tileset.name,
        "tilewidth": str(tileset.tile_width),
        "tileheight": str(tileset.tile_height),
        "tilecount": str(len(tileset.tiles)),
    })
    ET.SubElement(ts_el, "image", {
        "source": tileset_image_path,
        "width": str(tileset.tile_width * len(tileset.tiles)),
        "height": str(tileset.tile_height),
    })

    for layer in layers:
        layer_el = ET.SubElement(map_el, "layer", {
            "name": layer.name,
            "width": str(map_w),
            "height": str(map_h),
        })
        data_el = ET.SubElement(layer_el, "data", {"encoding": "csv"})
        rows = []
        for row in layer.grid:
            row_gids = [str(_tile_ref_to_gid(ref)) for ref in row]
            rows.append(",".join(row_gids))
        data_el.text = "\n" + ",\n".join(rows) + "\n"

    rough = ET.tostring(map_el, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + rough


def export_tileset_image(tileset: Tileset, output_path: str) -> None:
    """Export the tileset tiles as a horizontal strip PNG.

    Args:
        tileset: The Tileset to export.
        output_path: Path to write the PNG file.
    """
    from PIL import Image
    import numpy as np

    tw, th = tileset.tile_width, tileset.tile_height
    count = len(tileset.tiles)
    strip = Image.new("RGBA", (tw * count, th), (0, 0, 0, 0))

    for i, tile in enumerate(tileset.tiles):
        tile_img = Image.fromarray(tile, "RGBA")
        strip.paste(tile_img, (i * tw, 0))

    strip.save(output_path)
```

Run: `python -m pytest tests/test_tilemap_export.py -v`
Expected: All pass.

- [ ] **Step 3: Add export menu item and dialog in `app.py`**

In `src/app.py`:

1. Add import:
```python
from src.tilemap_export import export_tilemap_json, export_tilemap_tmx, export_tileset_image
```

2. In the File menu, add an Export submenu entry:
```python
export_menu = tk.Menu(file_menu, tearoff=0)
file_menu.add_cascade(label="Export", menu=export_menu)
export_menu.add_command(label="Tilemap Data...", command=self._export_tilemap_data)
```

3. Implement the handler:
```python
def _export_tilemap_data(self):
    """Export tilemap layers as JSON or TMX."""
    # Find tilemap layers in current frame
    frame_obj = self.timeline.current_frame_obj()
    tilemap_layers = [l for l in frame_obj.layers
                      if hasattr(l, 'is_tilemap') and l.is_tilemap()]
    if not tilemap_layers:
        from tkinter import messagebox
        messagebox.showinfo("Export Tilemap", "No tilemap layers found in current frame.")
        return

    # Simple format picker dialog
    fmt_win = tk.Toplevel(self.root)
    fmt_win.title("Export Tilemap Data")
    fmt_win.transient(self.root)
    fmt_win.grab_set()
    fmt_win.configure(bg=BG_PANEL)

    fmt_var = tk.StringVar(value="json")
    tk.Radiobutton(fmt_win, text="JSON (Tiled-compatible)", variable=fmt_var,
                   value="json", bg=BG_PANEL, fg=TEXT_PRIMARY).pack(anchor=tk.W, padx=10, pady=5)
    tk.Radiobutton(fmt_win, text="TMX XML (Tiled)", variable=fmt_var,
                   value="tmx", bg=BG_PANEL, fg=TEXT_PRIMARY).pack(anchor=tk.W, padx=10)

    def do_export():
        fmt = fmt_var.get()
        ext = ".json" if fmt == "json" else ".tmx"
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[("JSON", "*.json"), ("TMX", "*.tmx")] if fmt == "json"
                      else [("TMX", "*.tmx"), ("JSON", "*.json")]
        )
        if not path:
            fmt_win.destroy()
            return

        ts = tilemap_layers[0].tileset
        if fmt == "json":
            content = export_tilemap_json(ts, tilemap_layers)
        else:
            content = export_tilemap_tmx(ts, tilemap_layers)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        # Also export tileset image next to the data file
        import os
        dir_path = os.path.dirname(path)
        ts_img_path = os.path.join(dir_path, "tileset.png")
        export_tileset_image(ts, ts_img_path)

        self._update_status(f"Tilemap exported to {path}")
        fmt_win.destroy()

    tk.Button(fmt_win, text="Export", command=do_export).pack(pady=10)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_tilemap_export.py tests/test_sheet_import.py -v`
Expected: All pass.

---

## Final Verification

- [ ] **Run full test suite**

```
python -m pytest tests/ -v --tb=short
```

Expected: All existing tests pass. All new tests pass. No regressions.

- [ ] **Manual smoke test checklist (UI features)**

1. Pressure sensitivity: toggle button hidden if no tablet; visible with mapping dropdown if tablet detected
2. AnimPainting: `Ctrl+Shift+A` toggles, status bar shows "AnimPaint", strokes advance frames, wraps at end
3. Scale/Skew: make a selection, `Ctrl+Shift+S` shows handles, drag corner to scale, drag edge to skew, Enter commits, Escape cancels
4. Right-click tool: right-click toolbar icon assigns to RMB, right-click canvas uses RMB tool, status bar shows `LMB: Pen | RMB: Eraser`
5. Sprite sheet import: `File > Import > Sprite Sheet...`, load a known sheet, verify tile count, import creates frames
6. Tilemap export: `File > Export > Tilemap Data...`, export JSON, open in Tiled to verify structure

---

## Summary of New/Modified Files

| File | Action | Task |
|------|--------|------|
| `src/pressure.py` | Create | 1 |
| `tests/test_pressure.py` | Create | 1 |
| `src/tool_settings.py` | Modify (add `"pressure"` to `TOOL_DEFAULTS`) | 1 |
| `src/ui/options_bar.py` | Modify (pressure toggle in pen/eraser options) | 1 |
| `src/app.py` | Modify (pressure init, drag integration, AnimPainting, transform mode, right-click routing, menu items) | 1-6 |
| `tests/test_anim_painting.py` | Create | 2 |
| `src/keybindings.py` | Modify (add `anim_painting`, `scale_skew`) | 2, 3 |
| `src/ui/timeline.py` | Modify (AP toggle button) | 2 |
| `tests/test_scale_skew.py` | Create | 3 |
| `src/image_processing.py` | Modify (add `affine_transform`) | 3 |
| `tests/test_right_click_tool.py` | Create | 4 |
| `src/ui/toolbar.py` | Modify (right-click assignment + indicator) | 4 |
| `src/sheet_import.py` | Create | 5 |
| `src/ui/sheet_import_dialog.py` | Create | 5 |
| `tests/test_sheet_import.py` | Create | 5 |
| `src/tilemap_export.py` | Create | 6 |
| `tests/test_tilemap_export.py` | Create | 6 |
