# Movable Symmetry Axis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a visible, draggable symmetry axis guide line that persists per-project.

**Architecture:** Add axis state to `app.py`, update mirroring in `input_handler.py` to use axis vars instead of hardcoded center, draw axis overlay in `canvas.py`, save/load in `project.py`. Axis drag and right-click popup handled in `input_handler.py`.

**Tech Stack:** Python, Tkinter, existing canvas overlay system

**Spec:** `docs/superpowers/specs/2026-04-07-movable-symmetry-axis-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/app.py` | **Modify** | Axis state vars, reset on resize, draw axis after render |
| `src/input_handler.py` | **Modify** | Update `_apply_symmetry_draw`, axis drag, hit test, right-click popup |
| `src/canvas.py` | **Modify** | `draw_symmetry_axis()`, `clear_symmetry_axis()` |
| `src/project.py` | **Modify** | Save/load axis position |
| `tests/test_symmetry_axis.py` | **Create** | Mirroring with custom axis, save/load |

---

## Task 1: Axis State + Update Mirroring

**Files:**
- Modify: `src/app.py`
- Modify: `src/input_handler.py`
- Create: `tests/test_symmetry_axis.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_symmetry_axis.py
"""Tests for movable symmetry axis."""
import pytest
import numpy as np
from src.pixel_data import PixelGrid


def _apply_symmetry(fn, x, y, mode, axis_x, axis_y):
    """Standalone version of _apply_symmetry_draw for testing."""
    fn(x, y)
    cx = axis_x
    cy = axis_y
    if mode in ("horizontal", "both"):
        fn(2 * cx - x - 1, y)
    if mode in ("vertical", "both"):
        fn(x, 2 * cy - y - 1)
    if mode == "both":
        fn(2 * cx - x - 1, 2 * cy - y - 1)


class TestMirrorWithAxis:
    def test_horizontal_default_center(self):
        """Default center axis mirrors same as old behavior."""
        pixels = []
        _apply_symmetry(lambda x, y: pixels.append((x, y)),
                        2, 3, "horizontal", axis_x=5, axis_y=5)
        assert (2, 3) in pixels
        assert (7, 3) in pixels  # 2*5 - 2 - 1 = 7

    def test_horizontal_custom_axis(self):
        """Custom axis at x=3 mirrors differently."""
        pixels = []
        _apply_symmetry(lambda x, y: pixels.append((x, y)),
                        1, 5, "horizontal", axis_x=3, axis_y=5)
        assert (1, 5) in pixels
        assert (4, 5) in pixels  # 2*3 - 1 - 1 = 4

    def test_vertical_custom_axis(self):
        pixels = []
        _apply_symmetry(lambda x, y: pixels.append((x, y)),
                        5, 2, "vertical", axis_x=5, axis_y=4)
        assert (5, 2) in pixels
        assert (5, 5) in pixels  # 2*4 - 2 - 1 = 5

    def test_both_custom_axis(self):
        pixels = []
        _apply_symmetry(lambda x, y: pixels.append((x, y)),
                        1, 1, "both", axis_x=3, axis_y=3)
        assert len(pixels) == 4
        assert (1, 1) in pixels
        assert (4, 1) in pixels  # horiz
        assert (1, 4) in pixels  # vert
        assert (4, 4) in pixels  # both

    def test_axis_defaults_to_center(self):
        """Axis should default to canvas_dim // 2."""
        w, h = 32, 24
        assert w // 2 == 16
        assert h // 2 == 12
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_symmetry_axis.py -v`
Expected: PASS (these test the standalone formula, not app integration yet)

- [ ] **Step 3: Add axis state to app.py**

In `src/app.py`, find `self._symmetry_mode = "off"` (line 168). Add after it:

```python
        self._symmetry_axis_x = self.timeline.width // 2
        self._symmetry_axis_y = self.timeline.height // 2
        self._symmetry_axis_dragging = None  # "x", "y", or None
```

- [ ] **Step 4: Update _apply_symmetry_draw in input_handler.py**

Replace the method at line 682:

```python
    def _apply_symmetry_draw(self, fn, x, y):
        """Apply a draw function with symmetry mirroring."""
        fn(x, y)
        cx = self._symmetry_axis_x
        cy = self._symmetry_axis_y
        if self._symmetry_mode in ("horizontal", "both"):
            fn(2 * cx - x - 1, y)
        if self._symmetry_mode in ("vertical", "both"):
            fn(x, 2 * cy - y - 1)
        if self._symmetry_mode == "both":
            fn(2 * cx - x - 1, 2 * cy - y - 1)
```

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/app.py src/input_handler.py tests/test_symmetry_axis.py
git commit -m "feat: add symmetry axis state, update mirroring to use axis vars"
```

---

## Task 2: Canvas Axis Guide Drawing

**Files:**
- Modify: `src/canvas.py`
- Modify: `src/app.py`

- [ ] **Step 1: Add draw_symmetry_axis and clear_symmetry_axis to canvas.py**

Add after the `clear_transform_handles` method in `src/canvas.py`:

```python
    # --- Symmetry Axis Guide ---

    def draw_symmetry_axis(self, axis_x: int | None, axis_y: int | None,
                            canvas_w: int, canvas_h: int, zoom: int) -> None:
        """Draw dashed magenta axis guide lines.

        Args:
            axis_x: X position for vertical axis (None to skip)
            axis_y: Y position for horizontal axis (None to skip)
            canvas_w: Canvas width in grid pixels
            canvas_h: Canvas height in grid pixels
            zoom: pixel_size (screen pixels per grid pixel)
        """
        self.delete("symmetry_axis")
        color = "#ff00ff"

        if axis_x is not None:
            sx = axis_x * zoom
            self.create_line(sx, 0, sx, canvas_h * zoom,
                             fill=color, dash=(4, 4), width=1,
                             tags="symmetry_axis")

        if axis_y is not None:
            sy = axis_y * zoom
            self.create_line(0, sy, canvas_w * zoom, sy,
                             fill=color, dash=(4, 4), width=1,
                             tags="symmetry_axis")

        self.tag_raise("symmetry_axis")

    def clear_symmetry_axis(self) -> None:
        """Remove symmetry axis overlay."""
        self.delete("symmetry_axis")
```

- [ ] **Step 2: Draw axis after each canvas render**

In `src/app.py`, find `_render_canvas` (around line 961). After the render call and effects restore, add a call to draw the axis. Find the end of the method and add:

```python
        # Draw symmetry axis guide
        self._draw_symmetry_axis_overlay()
```

Also add a helper method. Since we can't add methods to app.py per CLAUDE.md rules, this needs to go in input_handler.py. Add to `InputHandlerMixin`:

```python
    def _draw_symmetry_axis_overlay(self):
        """Draw the symmetry axis guide line if symmetry is active."""
        if self._symmetry_mode == "off":
            self.pixel_canvas.clear_symmetry_axis()
            return
        w = self.timeline.width
        h = self.timeline.height
        ps = self.pixel_canvas.pixel_size
        axis_x = self._symmetry_axis_x if self._symmetry_mode in ("horizontal", "both") else None
        axis_y = self._symmetry_axis_y if self._symmetry_mode in ("vertical", "both") else None
        self.pixel_canvas.draw_symmetry_axis(axis_x, axis_y, w, h, ps)
```

Then in `_render_canvas` in `src/app.py`, add at the end:

```python
        self._draw_symmetry_axis_overlay()
```

Also add the same call at the end of `_refresh_canvas`.

- [ ] **Step 3: Run all tests**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add src/canvas.py src/app.py src/input_handler.py
git commit -m "feat: draw symmetry axis guide line on canvas"
```

---

## Task 3: Axis Drag Interaction

**Files:**
- Modify: `src/input_handler.py`
- Modify: `tests/test_symmetry_axis.py`

- [ ] **Step 1: Write failing test for hit testing**

```python
# Add to tests/test_symmetry_axis.py

class TestAxisHitTest:
    def test_hit_vertical_axis(self):
        """Click near vertical axis returns 'x'."""
        from src.input_handler import _hit_test_symmetry_axis
        result = _hit_test_symmetry_axis(10, 5, "horizontal", 10, 8, pixel_size=4)
        assert result == "x"

    def test_hit_horizontal_axis(self):
        from src.input_handler import _hit_test_symmetry_axis
        result = _hit_test_symmetry_axis(5, 8, "vertical", 10, 8, pixel_size=4)
        assert result == "y"

    def test_hit_miss(self):
        from src.input_handler import _hit_test_symmetry_axis
        result = _hit_test_symmetry_axis(0, 0, "horizontal", 10, 8, pixel_size=4)
        assert result is None

    def test_hit_off_mode(self):
        from src.input_handler import _hit_test_symmetry_axis
        result = _hit_test_symmetry_axis(10, 5, "off", 10, 8, pixel_size=4)
        assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_symmetry_axis.py::TestAxisHitTest -v`
Expected: FAIL — `ImportError: cannot import name '_hit_test_symmetry_axis'`

- [ ] **Step 3: Implement hit testing as a module-level function**

Add to `src/input_handler.py` as a module-level function (before the class, after imports):

```python
def _hit_test_symmetry_axis(canvas_x: int, canvas_y: int,
                             mode: str, axis_x: int, axis_y: int,
                             pixel_size: int, threshold: float = 6.0) -> str | None:
    """Test if canvas coordinates are near a symmetry axis line.

    Args:
        canvas_x, canvas_y: Position in grid pixels
        mode: Symmetry mode ("off", "horizontal", "vertical", "both")
        axis_x, axis_y: Axis positions in grid pixels
        pixel_size: Zoom level
        threshold: Hit distance in screen pixels

    Returns: "x" if near vertical axis, "y" if near horizontal axis, None otherwise.
    """
    if mode == "off":
        return None
    thresh_grid = threshold / pixel_size if pixel_size > 0 else threshold

    if mode in ("horizontal", "both"):
        if abs(canvas_x - axis_x) <= thresh_grid:
            return "x"
    if mode in ("vertical", "both"):
        if abs(canvas_y - axis_y) <= thresh_grid:
            return "y"
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_symmetry_axis.py::TestAxisHitTest -v`
Expected: PASS

- [ ] **Step 5: Add axis drag to mouse handlers**

In `_on_canvas_click`, add BEFORE the rotation mode check (around line 52):

```python
        # Symmetry axis drag
        if self._symmetry_mode != "off":
            axis_hit = _hit_test_symmetry_axis(
                x, y, self._symmetry_mode,
                self._symmetry_axis_x, self._symmetry_axis_y,
                self.pixel_canvas.pixel_size)
            if axis_hit is not None:
                self._symmetry_axis_dragging = axis_hit
                return
```

In `_on_canvas_drag`, add BEFORE the rotation drag check:

```python
        if self._symmetry_axis_dragging is not None:
            if self._symmetry_axis_dragging == "x":
                self._symmetry_axis_x = max(0, min(self.timeline.width, x))
            else:
                self._symmetry_axis_y = max(0, min(self.timeline.height, y))
            self._draw_symmetry_axis_overlay()
            return
```

In `_on_canvas_release`, add BEFORE the rotation release check:

```python
        if self._symmetry_axis_dragging is not None:
            self._symmetry_axis_dragging = None
            return
```

In `_on_canvas_motion`, add after `self._last_cursor_pos = (x, y)` and before any other checks:

```python
        # Symmetry axis cursor feedback
        if self._symmetry_mode != "off":
            axis_hit = _hit_test_symmetry_axis(
                x, y, self._symmetry_mode,
                self._symmetry_axis_x, self._symmetry_axis_y,
                self.pixel_canvas.pixel_size)
            if axis_hit == "x":
                self.pixel_canvas.config(cursor="sb_h_double_arrow")
            elif axis_hit == "y":
                self.pixel_canvas.config(cursor="sb_v_double_arrow")
```

Note: Don't return here — let normal cursor handling proceed if no axis hit. The cursor will be overridden by tool-specific cursors below.

- [ ] **Step 6: Run all tests**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add src/input_handler.py tests/test_symmetry_axis.py
git commit -m "feat: add symmetry axis drag interaction and hit testing"
```

---

## Task 4: Right-Click Popup for Precise Positioning

**Files:**
- Modify: `src/input_handler.py`

- [ ] **Step 1: Add right-click handler and popup**

Add right-click binding detection. In `_on_canvas_click`, the right-click needs to be detected. Check how the app binds mouse buttons — typically `<Button-3>` for right-click. 

Add a new method to `InputHandlerMixin`:

```python
    def _on_canvas_right_click(self, x, y):
        """Handle right-click on canvas — check for symmetry axis popup."""
        if self._symmetry_mode == "off":
            return
        axis_hit = _hit_test_symmetry_axis(
            x, y, self._symmetry_mode,
            self._symmetry_axis_x, self._symmetry_axis_y,
            self.pixel_canvas.pixel_size)
        if axis_hit is not None:
            self._show_axis_position_popup(axis_hit)

    def _show_axis_position_popup(self, axis: str):
        """Show a small popup for precise axis positioning."""
        from src.ui.theme import (
            ACCENT_CYAN, BG_DEEP, BG_PANEL_ALT,
            BUTTON_BG, BUTTON_HOVER, TEXT_PRIMARY, TEXT_SECONDARY,
        )

        popup = tk.Toplevel(self.root)
        popup.title("Axis Position")
        popup.configure(bg=BG_DEEP)
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()

        font = ("Consolas", 9)

        if axis == "x" or self._symmetry_mode == "both":
            row_x = tk.Frame(popup, bg=BG_DEEP)
            row_x.pack(fill="x", padx=10, pady=(10, 2))
            tk.Label(row_x, text="X:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                     font=font).pack(side="left")
            x_var = tk.IntVar(value=self._symmetry_axis_x)
            tk.Spinbox(row_x, from_=0, to=self.timeline.width, width=5,
                       textvariable=x_var, font=font,
                       bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                       buttonbackground=BUTTON_BG).pack(side="left", padx=4)

        if axis == "y" or self._symmetry_mode == "both":
            row_y = tk.Frame(popup, bg=BG_DEEP)
            row_y.pack(fill="x", padx=10, pady=2)
            tk.Label(row_y, text="Y:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                     font=font).pack(side="left")
            y_var = tk.IntVar(value=self._symmetry_axis_y)
            tk.Spinbox(row_y, from_=0, to=self.timeline.height, width=5,
                       textvariable=y_var, font=font,
                       bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                       buttonbackground=BUTTON_BG).pack(side="left", padx=4)

        btn_row = tk.Frame(popup, bg=BG_DEEP)
        btn_row.pack(fill="x", padx=10, pady=(6, 10))

        def _apply():
            if axis == "x" or self._symmetry_mode == "both":
                self._symmetry_axis_x = x_var.get()
            if axis == "y" or self._symmetry_mode == "both":
                self._symmetry_axis_y = y_var.get()
            popup.destroy()
            self._draw_symmetry_axis_overlay()

        tk.Button(btn_row, text="OK", bg=ACCENT_CYAN, fg=BG_DEEP,
                  font=("Consolas", 9, "bold"), relief="flat", padx=12,
                  command=_apply).pack(side="right", padx=4)
        tk.Button(btn_row, text="Cancel", bg=BUTTON_BG, fg=TEXT_PRIMARY,
                  font=font, relief="flat", padx=12,
                  command=popup.destroy).pack(side="right", padx=4)

        # Center on parent
        popup.update_idletasks()
        pw, ph = self.root.winfo_width(), self.root.winfo_height()
        px, py = self.root.winfo_rootx(), self.root.winfo_rooty()
        w, h = popup.winfo_width(), popup.winfo_height()
        popup.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")
```

- [ ] **Step 2: Bind right-click on canvas**

In `src/app.py`, find where `pixel_canvas` mouse bindings are set up. Look for `<Button-1>` bindings. Add a `<Button-3>` binding nearby:

```python
        self.pixel_canvas.bind("<Button-3>", lambda e: self._on_canvas_right_click(
            int(e.x // self.pixel_canvas.pixel_size),
            int(e.y // self.pixel_canvas.pixel_size)))
```

If `<Button-3>` is already bound to something else, integrate the axis check at the start of that handler.

- [ ] **Step 3: Run all tests**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add src/input_handler.py src/app.py
git commit -m "feat: add right-click popup for precise symmetry axis positioning"
```

---

## Task 5: Project Save/Load + Canvas Resize Reset

**Files:**
- Modify: `src/project.py`
- Modify: `src/app.py`
- Modify: `tests/test_symmetry_axis.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/test_symmetry_axis.py

class TestProjectSaveLoad:
    def test_axis_round_trip(self):
        """Axis position survives save/load cycle."""
        import json
        # Simulate the project data dict
        project_data = {
            "symmetry_axis_x": 7,
            "symmetry_axis_y": 12,
        }
        dumped = json.dumps(project_data)
        loaded = json.loads(dumped)
        assert loaded["symmetry_axis_x"] == 7
        assert loaded["symmetry_axis_y"] == 12

    def test_missing_axis_defaults(self):
        """Old projects without axis data default to None (caller uses center)."""
        project_data = {}
        assert project_data.get("symmetry_axis_x") is None
        assert project_data.get("symmetry_axis_y") is None
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_symmetry_axis.py::TestProjectSaveLoad -v`
Expected: PASS (these are self-contained data tests)

- [ ] **Step 3: Add axis to project save**

In `src/project.py`, in the `save_project` function, find where `project` dict is built (around line 158-176). Add after `"tool_settings"`:

```python
        "symmetry_axis_x": kwargs.get("symmetry_axis_x"),
        "symmetry_axis_y": kwargs.get("symmetry_axis_y"),
```

Update the `save_project` function signature to accept these:

```python
def save_project(filepath: str, timeline: AnimationTimeline,
                 palette: Palette, tool_settings: dict | None = None,
                 reference_image=None, grid_settings=None,
                 symmetry_axis_x: int | None = None,
                 symmetry_axis_y: int | None = None) -> None:
```

Add the axis fields to the project dict:

```python
    if symmetry_axis_x is not None:
        project["symmetry_axis_x"] = symmetry_axis_x
    if symmetry_axis_y is not None:
        project["symmetry_axis_y"] = symmetry_axis_y
```

- [ ] **Step 4: Add axis to project load**

In `load_project`, at the end (around line 339), read axis data and include in the return tuple's grid_data dict:

Actually, the simplest approach: return axis data in the existing `grid_data` dict. In `load_project`, around line 338-341:

```python
    grid_data = project.get("grid")
    symmetry_axis = {
        "x": project.get("symmetry_axis_x"),
        "y": project.get("symmetry_axis_y"),
    }
```

Then modify the return to include it. But to avoid changing the return type, pack it into grid_data. Actually, the cleanest approach: just read it in `file_ops.py` after loading.

In `src/file_ops.py`, find where `load_project` result is used. The axis values are simple ints in the project JSON — we can read them from the loaded data. Actually, `load_project` returns `(timeline, palette, tool_settings, ref, grid_data)`. Let's add axis to grid_data.

In `load_project` in `src/project.py`, around line 339:

```python
    grid_data = project.get("grid")
    # Attach symmetry axis to grid data for the caller
    if grid_data is None:
        grid_data = {}
    if isinstance(grid_data, dict):
        grid_data["symmetry_axis_x"] = project.get("symmetry_axis_x")
        grid_data["symmetry_axis_y"] = project.get("symmetry_axis_y")
```

- [ ] **Step 5: Wire save/load in file_ops.py**

In `src/file_ops.py`, update all `save_project` calls to pass axis data. Find each call (there are ~5) and add:

```python
                             symmetry_axis_x=self._symmetry_axis_x,
                             symmetry_axis_y=self._symmetry_axis_y,
```

In the project loading code in `src/app.py` (or `file_ops.py`), after restoring grid settings, read axis:

```python
        if grid_data:
            ax = grid_data.get("symmetry_axis_x")
            ay = grid_data.get("symmetry_axis_y")
            if ax is not None:
                self._symmetry_axis_x = ax
            if ay is not None:
                self._symmetry_axis_y = ay
```

- [ ] **Step 6: Reset axis on canvas resize**

Find the canvas resize handler (search for where `timeline.width` is changed). Add:

```python
        self._symmetry_axis_x = self.timeline.width // 2
        self._symmetry_axis_y = self.timeline.height // 2
```

- [ ] **Step 7: Run all tests**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add src/project.py src/file_ops.py src/app.py tests/test_symmetry_axis.py
git commit -m "feat: save/load symmetry axis position, reset on resize"
```

---

## Summary

| Task | What it builds | Tests |
|------|---------------|-------|
| 1 | Axis state + mirroring update | 5 |
| 2 | Canvas axis guide drawing | 0 (visual) |
| 3 | Axis drag + hit testing | 4 |
| 4 | Right-click precise popup | 0 (UI) |
| 5 | Project save/load + resize reset | 2 |
| **Total** | | **11 tests** |
