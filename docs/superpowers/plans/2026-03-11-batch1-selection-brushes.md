# Batch 1: Selection System & Custom Brushes — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify the selection model into a single pixel-set representation, add a freehand lasso tool, implement selection set operations (add/subtract/intersect), and enable custom brush capture from selections.

**Architecture:** All selection tools (rect, wand, lasso) produce `set[tuple[int,int]]` stored in `self._selection_pixels`. Selection operations use Python set operators. Custom brushes store a mask of relative offsets applied by PenTool/EraserTool instead of the default square footprint.

**Tech Stack:** Python 3.8+, NumPy, Tkinter, PIL/Pillow, pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/tools.py` | Modify | Add `LassoTool` class; add `mask` param to `PenTool.apply()` and `EraserTool.apply()` |
| `src/app.py` | Modify | Unify selection state; add lasso handlers; selection ops; custom brush capture/draw |
| `src/canvas.py` | Modify | Add `draw_lasso_preview()`; keep `draw_wand_selection()` as the single selection renderer |
| `src/ui/toolbar.py` | Modify | Add lasso tool button |
| `src/ui/options_bar.py` | Modify | Add `"lasso"` entry to `TOOL_OPTIONS` |
| `src/ui/icons.py` | Modify | Add lasso icon mapping |
| `tests/test_tools.py` | Modify | Tests for `LassoTool`, mask-based pen/eraser |
| `tests/test_selection.py` | Create | Tests for unified selection model and set operations |

---

## Chunk 1: Unified Selection Model

### Task 1: Unify selection state variables

**Files:**
- Modify: `src/app.py:96-102` (state variables)
- Modify: `src/app.py:771-777` (`_clear_selection`)

- [ ] **Step 1: Update state variables**

In `src/app.py`, replace the selection state block (lines 96-98):

```python
# Old:
self._select_start = None
self._selection = None
self._wand_selection = None

# New:
self._select_start = None
self._selection_pixels = None   # set[tuple[int,int]] or None — unified for all tools
```

Keep `_wand_tolerance`, `_clipboard`, `_pasting`, `_paste_pos` unchanged.

Also add `_paste_origin` initialization:

```python
self._paste_origin = (0, 0)       # origin for pasting copied selection
```

- [ ] **Step 2: Update `_clear_selection`**

In `src/app.py` (line ~771):

```python
def _clear_selection(self):
    """Clear the active selection."""
    self._selection_pixels = None
    self._select_start = None
    self.pixel_canvas.clear_selection()
    self.pixel_canvas.clear_overlays()
```

- [ ] **Step 3: Run tests to check what breaks**

Run: `python -m pytest tests/ -x -q 2>&1 | head -30`

This will show all references to `_selection` and `_wand_selection` that need updating. Fix each in the following tasks.

---

### Task 2: Migrate rect select to pixel set

**Files:**
- Modify: `src/app.py:616-620` (select click handler)
- Modify: `src/app.py:694-698` (select drag handler)
- Modify: `src/app.py:722-728` (select release handler)

- [ ] **Step 1: Update select tool click handler**

In `_on_canvas_click` (line ~616), replace:

```python
# Old:
elif self.current_tool_name == "Select":
    self._select_start = (x, y)
    self._selection = None
    self._wand_selection = None
    self.pixel_canvas.clear_selection()

# New:
elif self.current_tool_name == "Select":
    self._select_start = (x, y)
    shift_held = event_state & 0x1
    ctrl_held = event_state & 0x4
    if not shift_held and not ctrl_held:
        self._selection_pixels = None
        self.pixel_canvas.clear_selection()
```

- [ ] **Step 2: Update select tool release handler**

In `_on_canvas_release` (line ~722), replace:

```python
# Old:
elif self.current_tool_name == "Select" and self._select_start:
    sx, sy = self._select_start
    x0, y0 = min(sx, x), min(sy, y)
    x1, y1 = max(sx, x), max(sy, y)
    self._selection = (x0, y0, x1, y1)
    self._select_start = None
    self.pixel_canvas.draw_selection(x0, y0, x1, y1)

# New:
elif self.current_tool_name == "Select" and self._select_start:
    sx, sy = self._select_start
    x0, y0 = min(sx, x), min(sy, y)
    x1, y1 = max(sx, x), max(sy, y)
    w, h = self.timeline.width, self.timeline.height
    new_pixels = {(px, py) for px in range(max(0, x0), min(w, x1 + 1))
                  for py in range(max(0, y0), min(h, y1 + 1))}
    self._selection_pixels = self._apply_selection_op(new_pixels, event_state)
    self._select_start = None
    self.pixel_canvas.draw_wand_selection(self._selection_pixels)
```

Note: `_on_canvas_release` needs `event_state` passed through. Check how the release handler receives the event — it may need the event object forwarded.

- [ ] **Step 3: Add `_apply_selection_op` helper**

Add this method to `src/app.py` (after `_clear_selection`):

```python
def _apply_selection_op(self, new_pixels, event_state=0):
    """Apply selection operation based on modifier keys."""
    shift_held = event_state & 0x1
    ctrl_held = event_state & 0x4
    existing = self._selection_pixels or set()
    if shift_held and ctrl_held:
        return existing & new_pixels      # Intersect
    elif shift_held:
        return existing | new_pixels      # Add
    elif ctrl_held:
        return existing - new_pixels      # Subtract
    else:
        return new_pixels                 # Replace
```

- [ ] **Step 4: Verify event_state propagation in release handler**

Check `_handle_release` / `_on_canvas_release` signature. The release handler in canvas.py fires a callback — ensure `event.state` is passed through. In `src/canvas.py`, the release binding should pass event state. In `src/app.py`, `_on_canvas_release(x, y)` may need to become `_on_canvas_release(x, y, event_state=0)`.

Update `_handle_release` in `src/canvas.py` to pass `event.state`:
```python
# In the Canvas bind callback for ButtonRelease:
if self._on_release:
    self._on_release(gx, gy, event.state)
```

Update `_on_canvas_release` signature in `src/app.py`:
```python
def _on_canvas_release(self, x, y, event_state=0):
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/ -x -q 2>&1 | head -30`

---

### Task 3: Migrate wand tool to unified selection

**Files:**
- Modify: `src/app.py:592-615` (wand click handler)

- [ ] **Step 1: Update wand click handler**

In `_on_canvas_click` (line ~592), replace the wand section:

```python
# Old: stores in self._wand_selection and derives self._selection bounding box
# New:
elif self.current_tool_name == "Wand":
    wand = self._tools["wand"]
    new_pixels = wand.apply(grid, x, y, tolerance=self._wand_tolerance)
    if new_pixels:
        self._selection_pixels = self._apply_selection_op(new_pixels, event_state)
        self.pixel_canvas.draw_wand_selection(self._selection_pixels)
    else:
        if not (event_state & 0x1) and not (event_state & 0x4):
            self._selection_pixels = None
            self.pixel_canvas.clear_selection()
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/ -x -q 2>&1 | head -30`

---

### Task 4: Migrate copy/fill/delete to unified selection

**Files:**
- Modify: `src/app.py:786-837` (`_fill_selection`, `_delete_selection`, `_copy_selection`)

- [ ] **Step 1: Update `_fill_selection`**

```python
def _fill_selection(self):
    """Fill selection pixels with current color."""
    if not self._selection_pixels:
        return
    self._push_undo()
    color = self.palette.selected_color
    layer = self.timeline.current_layer()
    for (px, py) in self._selection_pixels:
        layer.pixels.set_pixel(px, py, color)
    self._render_canvas()
```

- [ ] **Step 2: Update `_delete_selection`**

```python
def _delete_selection(self):
    """Clear selection pixels to transparent."""
    if self._selection_pixels:
        self._push_undo()
        layer = self.timeline.current_layer()
        for (px, py) in self._selection_pixels:
            layer.pixels.set_pixel(px, py, (0, 0, 0, 0))
        self._render_canvas()
    elif self.timeline.frame_count > 1:
        self._delete_frame()
```

- [ ] **Step 3: Update `_copy_selection`**

```python
def _copy_selection(self):
    """Copy selected pixels to clipboard."""
    if not self._selection_pixels:
        return
    # Compute bounding box of selection
    xs = [p[0] for p in self._selection_pixels]
    ys = [p[1] for p in self._selection_pixels]
    x0, y0 = min(xs), min(ys)
    x1, y1 = max(xs), max(ys)
    w = x1 - x0 + 1
    h = y1 - y0 + 1
    grid = self.timeline.current_frame()
    clip = PixelGrid(w, h)
    for (px, py) in self._selection_pixels:
        color = grid.get_pixel(px, py)
        clip.set_pixel(px - x0, py - y0, color)
    self._clipboard = clip
    self._paste_origin = (x0, y0)
```

- [ ] **Step 4: Update `_paste_clipboard` to use `_paste_origin`**

In the paste method, use `self._paste_origin` (if set) instead of deriving from `self._selection`:

```python
def _paste_clipboard(self):
    if self._clipboard is None:
        return
    self._pasting = True
    origin = self._paste_origin
    self._paste_pos = origin
    self._clear_selection()
    self.pixel_canvas.draw_floating_pixels(
        self._clipboard, origin[0], origin[1])
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/ -x -q 2>&1 | head -30`

---

### Task 5: Update `_refresh_canvas` and `_render_canvas` selection re-drawing

**Files:**
- Modify: `src/app.py:1561-1589` (render methods)

- [ ] **Step 1: Update selection redraw logic**

In both `_refresh_canvas` and `_render_canvas`, replace dual selection redraw:

```python
# Old pattern:
if self._wand_selection:
    self.pixel_canvas.draw_wand_selection(self._wand_selection)
elif self._selection:
    self.pixel_canvas.draw_selection(*self._selection)

# New (in both methods):
if self._selection_pixels:
    self.pixel_canvas.draw_wand_selection(self._selection_pixels)
```

- [ ] **Step 2: Search and fix all remaining references to `_selection` and `_wand_selection`**

Run: `grep -n "_selection\b\|_wand_selection" src/app.py`

Every hit should now reference `_selection_pixels` instead. Key locations to fix:

- **`_reset_state` (~line 1333):** Replace `self._selection = None` and `self._wand_selection = None` with `self._selection_pixels = None`
- **`_on_f_key` (~line 779):** Replace `if self._selection:` with `if self._selection_pixels:`
- **`_paste_clipboard` (~line 845):** Replace `self._selection` origin reference with `self._paste_origin`
- Any other occurrences in auto-save state checks, project load/save.

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -q 2>&1`
Expected: All tests pass (some may need updating if they reference old selection vars)

- [ ] **Step 4: Commit**

```bash
git add src/app.py src/canvas.py
git commit -m "refactor: unify selection model to single pixel-set representation

Replace _selection (rect tuple) and _wand_selection (pixel set) with
unified _selection_pixels. Add _apply_selection_op for add/subtract/intersect.
All selection tools now produce pixel sets with consistent modifier behavior."
```

---

### Task 6: Write tests for unified selection model

**Files:**
- Create: `tests/test_selection.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for the unified selection model and set operations."""
import pytest
from src.pixel_data import PixelGrid


class TestSelectionOperations:
    """Test selection set operations (add/subtract/intersect)."""

    def _make_app_stub(self):
        """Create a minimal stub with selection state."""
        class Stub:
            _selection_pixels = None
            def _apply_selection_op(self, new_pixels, event_state=0):
                shift_held = event_state & 0x1
                ctrl_held = event_state & 0x4
                existing = self._selection_pixels or set()
                if shift_held and ctrl_held:
                    return existing & new_pixels
                elif shift_held:
                    return existing | new_pixels
                elif ctrl_held:
                    return existing - new_pixels
                else:
                    return new_pixels
        return Stub()

    def test_replace_selection(self):
        stub = self._make_app_stub()
        stub._selection_pixels = {(0, 0), (1, 1)}
        result = stub._apply_selection_op({(2, 2), (3, 3)}, event_state=0)
        assert result == {(2, 2), (3, 3)}

    def test_add_selection_shift(self):
        stub = self._make_app_stub()
        stub._selection_pixels = {(0, 0), (1, 1)}
        result = stub._apply_selection_op({(2, 2)}, event_state=0x1)
        assert result == {(0, 0), (1, 1), (2, 2)}

    def test_subtract_selection_ctrl(self):
        stub = self._make_app_stub()
        stub._selection_pixels = {(0, 0), (1, 1), (2, 2)}
        result = stub._apply_selection_op({(1, 1)}, event_state=0x4)
        assert result == {(0, 0), (2, 2)}

    def test_intersect_selection_shift_ctrl(self):
        stub = self._make_app_stub()
        stub._selection_pixels = {(0, 0), (1, 1), (2, 2)}
        result = stub._apply_selection_op({(1, 1), (3, 3)}, event_state=0x5)
        assert result == {(1, 1)}

    def test_add_to_empty(self):
        stub = self._make_app_stub()
        result = stub._apply_selection_op({(5, 5)}, event_state=0x1)
        assert result == {(5, 5)}

    def test_subtract_from_empty(self):
        stub = self._make_app_stub()
        result = stub._apply_selection_op({(5, 5)}, event_state=0x4)
        assert result == set()

    def test_rect_to_pixel_set(self):
        """Rect select should produce correct pixel set."""
        x0, y0, x1, y1 = 2, 3, 4, 5
        w, h = 10, 10
        pixels = {(px, py) for px in range(max(0, x0), min(w, x1 + 1))
                  for py in range(max(0, y0), min(h, y1 + 1))}
        assert len(pixels) == 3 * 3  # 3 wide × 3 tall
        assert (2, 3) in pixels
        assert (4, 5) in pixels
        assert (5, 5) not in pixels
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_selection.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_selection.py
git commit -m "test: add selection set operations tests"
```

---

## Chunk 2: Lasso Tool

### Task 7: Implement LassoTool with scanline fill

**Files:**
- Modify: `src/tools.py` (add LassoTool class)
- Create: Add tests in `tests/test_tools.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_tools.py`:

```python
from src.tools import LassoTool


class TestLassoTool:
    def test_fill_interior_square(self):
        """A square polygon should fill all interior pixels."""
        points = [(1, 1), (4, 1), (4, 4), (1, 4)]
        result = LassoTool.fill_interior(points, 10, 10)
        # Should include all pixels inside the square
        for x in range(1, 5):
            for y in range(1, 5):
                assert (x, y) in result, f"Missing ({x},{y})"

    def test_fill_interior_triangle(self):
        """A triangle should fill interior pixels."""
        points = [(5, 0), (9, 9), (0, 9)]
        result = LassoTool.fill_interior(points, 10, 10)
        assert (5, 5) in result   # center
        assert (0, 0) not in result  # outside

    def test_fill_interior_single_pixel(self):
        """Degenerate case: a single point."""
        points = [(3, 3)]
        result = LassoTool.fill_interior(points, 10, 10)
        assert (3, 3) in result

    def test_fill_interior_empty(self):
        """No points returns empty set."""
        result = LassoTool.fill_interior([], 10, 10)
        assert result == set()

    def test_fill_interior_clamps_to_canvas(self):
        """Points outside canvas are clamped."""
        points = [(-2, -2), (3, -2), (3, 3), (-2, 3)]
        result = LassoTool.fill_interior(points, 5, 5)
        assert (0, 0) in result
        assert (-1, -1) not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tools.py::TestLassoTool -v`
Expected: FAIL — `ImportError: cannot import name 'LassoTool'`

- [ ] **Step 3: Implement LassoTool**

Add to `src/tools.py` after the `MagicWandTool` class:

```python
class LassoTool:
    """Freehand lasso selection — converts a closed polygon to a pixel set."""

    @staticmethod
    def fill_interior(points: list, canvas_w: int, canvas_h: int) -> set:
        """Return set of (x, y) pixels inside the polygon using scanline fill.

        Uses the ray-casting (even-odd) rule: for each row, find edge
        crossings and fill between pairs.
        """
        if not points:
            return set()
        if len(points) < 3:
            return {(max(0, min(p[0], canvas_w - 1)),
                     max(0, min(p[1], canvas_h - 1))) for p in points}

        result = set()
        # Also include the boundary pixels
        n = len(points)
        for i in range(n):
            x0, y0 = points[i]
            x1, y1 = points[(i + 1) % n]
            # Bresenham to get boundary pixels
            dx = abs(x1 - x0)
            dy = abs(y1 - y0)
            sx = 1 if x1 > x0 else -1
            sy = 1 if y1 > y0 else -1
            err = dx - dy
            cx, cy = x0, y0
            while True:
                if 0 <= cx < canvas_w and 0 <= cy < canvas_h:
                    result.add((cx, cy))
                if cx == x1 and cy == y1:
                    break
                e2 = 2 * err
                if e2 > -dy:
                    err -= dy
                    cx += sx
                if e2 < dx:
                    err += dx
                    cy += sy

        # Scanline fill interior
        ys = [p[1] for p in points]
        y_min = max(0, min(ys))
        y_max = min(canvas_h - 1, max(ys))

        for y in range(y_min, y_max + 1):
            # Find x-intersections with polygon edges
            intersections = []
            for i in range(n):
                y0 = points[i][1]
                y1 = points[(i + 1) % n][1]
                x0 = points[i][0]
                x1 = points[(i + 1) % n][0]
                if y0 == y1:
                    continue
                if min(y0, y1) <= y < max(y0, y1):
                    x_int = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                    intersections.append(x_int)

            intersections.sort()
            # Fill between pairs
            for j in range(0, len(intersections) - 1, 2):
                x_start = max(0, int(intersections[j]))
                x_end = min(canvas_w - 1, int(intersections[j + 1]))
                for x in range(x_start, x_end + 1):
                    result.add((x, y))

        return result
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_tools.py::TestLassoTool -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/tools.py tests/test_tools.py
git commit -m "feat: add LassoTool with scanline polygon fill"
```

---

### Task 8: Add lasso to toolbar and options bar

**Files:**
- Modify: `src/ui/icons.py:11-23` (TOOL_ICON_MAP)
- Modify: `src/ui/options_bar.py:11-23` (TOOL_OPTIONS)
- Modify: `src/app.py` (tool instantiation, import)

- [ ] **Step 1: Add lasso to icon map**

In `src/ui/icons.py`, add to `TOOL_ICON_MAP`:

```python
"lasso": "lasso-bold.svg",
```

If `lasso-bold.svg` doesn't exist in the icons directory, the fallback letter icon ("L") will be used automatically.

- [ ] **Step 2: Add lasso to options bar**

In `src/ui/options_bar.py`, add to `TOOL_OPTIONS`:

```python
"lasso": {},
```

- [ ] **Step 3: Add LassoTool import and instance**

In `src/app.py`, add `LassoTool` to the import from `src.tools` (line ~11-15).

In the `_tools` dict initialization, add:

```python
"Lasso": LassoTool(),
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/ -q 2>&1 | tail -5`

- [ ] **Step 5: Commit**

```bash
git add src/ui/icons.py src/ui/options_bar.py src/app.py
git commit -m "feat: add lasso tool to toolbar and options bar"
```

---

### Task 9: Wire lasso mouse handlers

**Files:**
- Modify: `src/app.py` (click/drag/release handlers)
- Modify: `src/canvas.py` (add `draw_lasso_preview`)

- [ ] **Step 1: Add lasso state variable**

In `src/app.py` init, add:

```python
self._lasso_points = []    # list of (x, y) during lasso drag
```

- [ ] **Step 2: Add lasso preview to canvas**

In `src/canvas.py`, add method:

```python
def draw_lasso_preview(self, points: list) -> None:
    """Draw the in-progress lasso path as overlay lines."""
    self.delete("overlay")
    if len(points) < 2:
        return
    ps = self.pixel_size
    for i in range(len(points) - 1):
        x0 = points[i][0] * ps + ps // 2
        y0 = points[i][1] * ps + ps // 2
        x1 = points[i + 1][0] * ps + ps // 2
        y1 = points[i + 1][1] * ps + ps // 2
        self.create_line(x0, y0, x1, y1, fill="#00f0ff",
                         dash=(3, 3), width=1, tags="overlay")
```

- [ ] **Step 3: Handle lasso click**

In `_on_canvas_click`, add before the final `else`:

```python
elif self.current_tool_name == "Lasso":
    self._lasso_points = [(x, y)]
    shift_held = event_state & 0x1
    ctrl_held = event_state & 0x4
    if not shift_held and not ctrl_held:
        self._selection_pixels = None
        self.pixel_canvas.clear_selection()
```

- [ ] **Step 4: Handle lasso drag**

In `_on_canvas_drag`, add:

```python
elif self.current_tool_name == "Lasso" and self._lasso_points:
    self._lasso_points.append((x, y))
    self.pixel_canvas.draw_lasso_preview(self._lasso_points)
```

- [ ] **Step 5: Handle lasso release**

In `_on_canvas_release`, add:

```python
elif self.current_tool_name == "Lasso" and self._lasso_points:
    self._lasso_points.append((x, y))
    lasso = self._tools["Lasso"]
    w, h = self.timeline.width, self.timeline.height
    new_pixels = lasso.fill_interior(self._lasso_points, w, h)
    if new_pixels:
        self._selection_pixels = self._apply_selection_op(new_pixels, event_state)
        self.pixel_canvas.draw_wand_selection(self._selection_pixels)
    self._lasso_points = []
    self.pixel_canvas.clear_overlays()
```

- [ ] **Step 6: Clear lasso state on tool change**

In `_on_tool_change` (line ~436), add:

```python
self._lasso_points = []
```

- [ ] **Step 7: Run tests and manual smoke test**

Run: `python -m pytest tests/ -q 2>&1 | tail -5`
Manual: Launch app, select lasso tool, draw a shape, verify selection appears.

- [ ] **Step 8: Commit**

```bash
git add src/app.py src/canvas.py
git commit -m "feat: wire lasso tool mouse handlers with preview and selection"
```

---

## Chunk 3: Custom Brushes

### Task 10: Add mask parameter to PenTool and EraserTool

**Files:**
- Modify: `src/tools.py:27-49` (PenTool, EraserTool)
- Add tests to: `tests/test_tools.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_tools.py`:

```python
class TestCustomBrushMask:
    def test_pen_with_mask(self):
        """Pen should draw only at mask offset positions."""
        grid = PixelGrid(10, 10)
        pen = PenTool()
        mask = {(0, 0), (1, 0), (0, 1)}  # L-shape relative offsets
        color = (255, 0, 0, 255)
        pen.apply(grid, 5, 5, color, mask=mask)
        assert grid.get_pixel(5, 5) == color
        assert grid.get_pixel(6, 5) == color
        assert grid.get_pixel(5, 6) == color
        assert grid.get_pixel(6, 6) == (0, 0, 0, 0)  # not in mask

    def test_eraser_with_mask(self):
        """Eraser should clear only at mask offset positions."""
        grid = PixelGrid(10, 10)
        # Fill some pixels
        for x in range(10):
            for y in range(10):
                grid.set_pixel(x, y, (255, 0, 0, 255))
        eraser = EraserTool()
        mask = {(0, 0), (-1, 0)}
        eraser.apply(grid, 5, 5, mask=mask)
        assert grid.get_pixel(5, 5) == (0, 0, 0, 0)
        assert grid.get_pixel(4, 5) == (0, 0, 0, 0)
        assert grid.get_pixel(6, 5) == (255, 0, 0, 255)  # not in mask

    def test_pen_mask_clips_to_canvas(self):
        """Mask offsets outside canvas bounds are silently skipped."""
        grid = PixelGrid(5, 5)
        pen = PenTool()
        mask = {(-1, 0), (0, 0), (1, 0)}
        pen.apply(grid, 0, 0, (255, 255, 255, 255), mask=mask)
        assert grid.get_pixel(0, 0) == (255, 255, 255, 255)
        assert grid.get_pixel(1, 0) == (255, 255, 255, 255)
        # (-1, 0) should not crash — just skipped
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tools.py::TestCustomBrushMask -v`
Expected: FAIL — `TypeError: apply() got an unexpected keyword argument 'mask'`

- [ ] **Step 3: Update PenTool**

```python
class PenTool:
    def apply(self, grid: PixelGrid, x: int, y: int, color: tuple,
              size: int = 1, dither_pattern: str = "none",
              mask: set | None = None) -> None:
        if mask is not None:
            for dx, dy in mask:
                grid.set_pixel(x + dx, y + dy, color)
            return
        if size == 1:
            grid.set_pixel(x, y, color)
        else:
            _set_thick(grid, x, y, color, size)
```

Note: dither is applied at the app level before calling `apply`, not inside PenTool itself. Check existing dither logic to confirm. If dither is handled inside PenTool, preserve that path when mask is None.

Actually, re-check the existing PenTool (lines 27-40). The current implementation:

```python
class PenTool:
    def apply(self, grid: PixelGrid, x: int, y: int, color: tuple,
              size: int = 1, dither_pattern: str = "none") -> None:
        pattern = DITHER_PATTERNS.get(dither_pattern)
        if pattern is not None:
            if not pattern[y % len(pattern)][x % len(pattern[0])]:
                return
        if size == 1:
            grid.set_pixel(x, y, color)
        else:
            _set_thick(grid, x, y, color, size)
```

Dither IS handled in PenTool. Updated implementation with mask + dither:

```python
class PenTool:
    def apply(self, grid: PixelGrid, x: int, y: int, color: tuple,
              size: int = 1, dither_pattern: str = "none",
              mask: set | None = None) -> None:
        pattern = DITHER_PATTERNS.get(dither_pattern)
        if mask is not None:
            for dx, dy in mask:
                px, py = x + dx, y + dy
                if pattern is not None:
                    if not pattern[py % len(pattern)][px % len(pattern[0])]:
                        continue
                grid.set_pixel(px, py, color)
            return
        if pattern is not None:
            if not pattern[y % len(pattern)][x % len(pattern[0])]:
                return
        if size == 1:
            grid.set_pixel(x, y, color)
        else:
            _set_thick(grid, x, y, color, size)
```

- [ ] **Step 4: Update EraserTool**

```python
class EraserTool:
    def apply(self, grid: PixelGrid, x: int, y: int,
              size: int = 1, mask: set | None = None) -> None:
        if mask is not None:
            for dx, dy in mask:
                grid.set_pixel(x + dx, y + dy, (0, 0, 0, 0))
            return
        half = size // 2
        for dy in range(-half, -half + size):
            for dx in range(-half, -half + size):
                grid.set_pixel(x + dx, y + dy, (0, 0, 0, 0))
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_tools.py::TestCustomBrushMask -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/tools.py tests/test_tools.py
git commit -m "feat: add mask parameter to PenTool and EraserTool for custom brushes"
```

---

### Task 11: Implement brush capture and drawing integration

**Files:**
- Modify: `src/app.py` (state, menu, capture logic, draw routing)

- [ ] **Step 1: Add brush state variables**

In `src/app.py` init, add:

```python
self._custom_brush_mask = None   # set[tuple[int,int]] relative offsets or None
```

- [ ] **Step 2: Add menu entries**

In the Edit menu (after "Paste" / line ~196), add:

```python
edit_menu.add_separator()
edit_menu.add_command(label="Capture Brush", command=self._capture_brush,
                      accelerator="Ctrl+B")
edit_menu.add_command(label="Reset Brush", command=self._reset_brush)
```

Add keybinding:

```python
self.root.bind("<Control-b>", lambda e: self._capture_brush())
```

- [ ] **Step 3: Implement `_capture_brush`**

```python
def _capture_brush(self):
    """Capture selected pixels as a custom brush shape."""
    if not self._selection_pixels:
        return
    # Compute center of selection
    xs = [p[0] for p in self._selection_pixels]
    ys = [p[1] for p in self._selection_pixels]
    cx = (min(xs) + max(xs)) // 2
    cy = (min(ys) + max(ys)) // 2
    # Store as relative offsets from center
    grid = self.timeline.current_frame()
    mask = set()
    for (px, py) in self._selection_pixels:
        color = grid.get_pixel(px, py)
        if color[3] > 0:  # only include non-transparent pixels
            mask.add((px - cx, py - cy))
    if mask:
        self._custom_brush_mask = mask
        self._update_status(f"Custom brush: {len(mask)} pixels")
    self._clear_selection()
```

- [ ] **Step 4: Implement `_reset_brush`**

```python
def _reset_brush(self):
    """Reset to default square brush."""
    self._custom_brush_mask = None
    self._update_status("Brush reset to default")
```

- [ ] **Step 5: Update pen drawing to use custom mask**

In `_on_canvas_click` and `_on_canvas_drag`, where pen tool calls `apply`, pass the mask. Find the pen draw lambda (used in `_apply_symmetry_draw`). The current pattern is:

```python
# Current (approximate):
def draw_fn(dx, dy):
    self._tools["pen"].apply(layer.pixels, dx, dy, color,
                             size=self._tool_size,
                             dither_pattern=self._dither_pattern)

self._apply_symmetry_draw(draw_fn, x, y)
```

Update to pass mask:

```python
def draw_fn(dx, dy):
    self._tools["pen"].apply(layer.pixels, dx, dy, color,
                             size=self._tool_size,
                             dither_pattern=self._dither_pattern,
                             mask=self._custom_brush_mask)
```

Do the same for eraser:

```python
def erase_fn(dx, dy):
    self._tools["eraser"].apply(layer.pixels, dx, dy,
                                size=self._tool_size,
                                mask=self._custom_brush_mask)
```

- [ ] **Step 6: Reset custom brush on size change**

In the size change callback (options bar), add:

```python
self._custom_brush_mask = None
```

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/ -q 2>&1 | tail -5`

- [ ] **Step 8: Manual smoke test**

Launch app → draw some pixels → select with rect or wand → Ctrl+B to capture → switch to pen → draw with custom brush shape → Reset Brush → verify square brush returns.

- [ ] **Step 9: Commit**

```bash
git add src/app.py
git commit -m "feat: custom brush capture from selection and drawing integration"
```

---

### Task 12: Final integration test and cleanup

**Files:**
- Modify: `tests/test_selection.py` (add integration tests)

- [ ] **Step 1: Add integration tests**

```python
class TestSelectionIntegration:
    """Integration tests for selection + copy + fill with unified model."""

    def test_fill_pixel_set(self):
        """Filling a pixel-set selection should only affect those pixels."""
        grid = PixelGrid(10, 10)
        selection = {(2, 2), (3, 3), (4, 4)}
        color = (255, 0, 0, 255)
        for (px, py) in selection:
            grid.set_pixel(px, py, color)
        assert grid.get_pixel(2, 2) == color
        assert grid.get_pixel(0, 0) == (0, 0, 0, 0)

    def test_delete_pixel_set(self):
        """Deleting a pixel-set selection should clear to transparent."""
        grid = PixelGrid(10, 10)
        for x in range(10):
            for y in range(10):
                grid.set_pixel(x, y, (100, 100, 100, 255))
        selection = {(5, 5), (6, 6)}
        for (px, py) in selection:
            grid.set_pixel(px, py, (0, 0, 0, 0))
        assert grid.get_pixel(5, 5) == (0, 0, 0, 0)
        assert grid.get_pixel(4, 4) == (100, 100, 100, 255)

    def test_copy_from_pixel_set(self):
        """Copy from arbitrary pixel set should extract bounding box."""
        grid = PixelGrid(10, 10)
        grid.set_pixel(2, 3, (255, 0, 0, 255))
        grid.set_pixel(4, 5, (0, 255, 0, 255))
        selection = {(2, 3), (4, 5)}
        xs = [p[0] for p in selection]
        ys = [p[1] for p in selection]
        x0, y0 = min(xs), min(ys)
        x1, y1 = max(xs), max(ys)
        w = x1 - x0 + 1
        h = y1 - y0 + 1
        clip = PixelGrid(w, h)
        for (px, py) in selection:
            color = grid.get_pixel(px, py)
            clip.set_pixel(px - x0, py - y0, color)
        assert clip.get_pixel(0, 0) == (255, 0, 0, 255)
        assert clip.get_pixel(2, 2) == (0, 255, 0, 255)
        assert clip.get_pixel(1, 1) == (0, 0, 0, 0)  # not in selection
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v 2>&1 | tail -20`
Expected: All pass

- [ ] **Step 3: Final commit**

```bash
git add tests/test_selection.py
git commit -m "test: add integration tests for unified selection model"
```
