# Competitive Features Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add six features that close the highest-impact competitive gaps: Polygon tool, Rounded Rectangle tool, Contour Fill mode, Move tool, Linked Cels, and Clipping Masks.

**Architecture:** Batch A (tasks 1-4) adds four drawing tools following existing patterns — tool class in `src/tools.py`, event handling in `src/app.py`, toolbar/icons/options_bar registration. Batch B (tasks 5-6) modifies the layer/animation system to support linked cels (shared pixel references across frames) and clipping masks (alpha-based layer masking in compositing).

**Tech Stack:** Python, Tkinter, NumPy, PIL (existing stack). No new dependencies.

---

## Chunk 1: Drawing Tools (Batch A)

### Task 1: Polygon Tool

**Files:**
- Modify: `src/tools.py` (add class after `EllipseTool`, ~line 278)
- Test: `tests/test_polygon_tool.py` (create)
- Modify: `src/ui/icons.py` (add to TOOL_ICON_MAP, line 11)
- Modify: `src/ui/toolbar.py` (TOOL_LIST auto-derives from icon map)
- Modify: `src/ui/options_bar.py` (add "polygon" to TOOL_OPTIONS, line 11)
- Modify: `src/tool_settings.py` (add "polygon" to TOOL_DEFAULTS, line 11)
- Modify: `src/app.py` (add tool registration + event handlers)

**Step 1: Write failing tests**

Create `tests/test_polygon_tool.py`:

```python
"""Tests for PolygonTool."""
import numpy as np
from src.pixel_data import PixelGrid
from src.tools import PolygonTool


def test_polygon_outline_triangle():
    grid = PixelGrid(10, 10)
    tool = PolygonTool()
    points = [(1, 1), (8, 1), (4, 8)]
    tool.apply(grid, points, (255, 0, 0, 255), filled=False)
    # Vertices should be colored
    assert grid.get_pixel(1, 1) == (255, 0, 0, 255)
    assert grid.get_pixel(8, 1) == (255, 0, 0, 255)
    assert grid.get_pixel(4, 8) == (255, 0, 0, 255)
    # Center should be empty (outline only)
    assert grid.get_pixel(4, 4) == (0, 0, 0, 0)


def test_polygon_filled_triangle():
    grid = PixelGrid(10, 10)
    tool = PolygonTool()
    points = [(1, 1), (8, 1), (4, 8)]
    tool.apply(grid, points, (0, 255, 0, 255), filled=True)
    # Center should be filled
    assert grid.get_pixel(4, 3) == (0, 255, 0, 255)
    # Outside should be empty
    assert grid.get_pixel(0, 9) == (0, 0, 0, 0)


def test_polygon_outline_square():
    grid = PixelGrid(10, 10)
    tool = PolygonTool()
    points = [(2, 2), (7, 2), (7, 7), (2, 7)]
    tool.apply(grid, points, (255, 255, 0, 255), filled=False)
    # Top edge pixel
    assert grid.get_pixel(4, 2) == (255, 255, 0, 255)
    # Center should be empty
    assert grid.get_pixel(4, 4) == (0, 0, 0, 0)


def test_polygon_two_points_draws_line():
    grid = PixelGrid(10, 10)
    tool = PolygonTool()
    points = [(1, 1), (5, 1)]
    tool.apply(grid, points, (255, 0, 0, 255), filled=False)
    assert grid.get_pixel(3, 1) == (255, 0, 0, 255)


def test_polygon_single_point_draws_pixel():
    grid = PixelGrid(10, 10)
    tool = PolygonTool()
    points = [(3, 3)]
    tool.apply(grid, points, (255, 0, 0, 255), filled=False)
    assert grid.get_pixel(3, 3) == (255, 0, 0, 255)


def test_polygon_with_width():
    grid = PixelGrid(20, 20)
    tool = PolygonTool()
    points = [(5, 5), (15, 5), (10, 15)]
    tool.apply(grid, points, (255, 0, 0, 255), filled=False, width=3)
    # Adjacent pixels to edge should also be colored due to width
    assert grid.get_pixel(10, 5) == (255, 0, 0, 255)
    assert grid.get_pixel(10, 4) == (255, 0, 0, 255)  # one pixel above edge
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_polygon_tool.py -v`
Expected: FAIL — `ImportError: cannot import name 'PolygonTool'`

- [ ] **Step 3: Write PolygonTool implementation**

Add to `src/tools.py` after the `EllipseTool` class (before `MagicWandTool` at line 280):

```python
class PolygonTool:
    """Draw arbitrary polygons — outline or filled."""

    @staticmethod
    def apply(grid, points: list[tuple[int, int]], color: tuple,
              filled: bool = False, width: int = 1) -> None:
        if not points:
            return
        if len(points) == 1:
            _set_thick(grid, points[0][0], points[0][1], color, width)
            return

        if filled and len(points) >= 3:
            # Scanline fill only (no outline strokes)
            _polygon_scanfill(grid, points, color)
        else:
            # Draw outline edges
            line = LineTool()
            for i in range(len(points)):
                x0, y0 = points[i]
                x1, y1 = points[(i + 1) % len(points)]
                line.apply(grid, x0, y0, x1, y1, color, width=width)

def _polygon_scanfill(grid, points, color):
    """Even-odd scanline fill for a polygon."""
    ys = [p[1] for p in points]
    min_y = max(0, min(ys))
    max_y = min(grid.height - 1, max(ys))

    for y in range(min_y, max_y + 1):
        intersections = []
        n = len(points)
        for i in range(n):
            x0, y0 = points[i]
            x1, y1 = points[(i + 1) % n]
            if y0 == y1:
                continue
            if y0 > y1:
                x0, y0, x1, y1 = x1, y1, x0, y0
            if y < y0 or y >= y1:
                continue
            # X intersection
            t = (y - y0) / (y1 - y0)
            ix = x0 + t * (x1 - x0)
            intersections.append(ix)

        intersections.sort()
        # Fill between pairs (even-odd rule)
        for j in range(0, len(intersections) - 1, 2):
            x_start = max(0, int(intersections[j] + 0.5))
            x_end = min(grid.width - 1, int(intersections[j + 1] + 0.5))
            for x in range(x_start, x_end + 1):
                grid.set_pixel(x, y, color)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_polygon_tool.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Register Polygon in toolbar, icons, options_bar, and tool_settings**

In `src/ui/icons.py`, add to `TOOL_ICON_MAP` (after `"lasso"` entry):
```python
    "polygon": "polygon-bold.svg",
```

In `src/ui/icons.py`, add to `_PNG_FALLBACK` dict:
```python
    "polygon": "N",
```

In `src/ui/options_bar.py`, add to `TOOL_OPTIONS` (after `"lasso"` entry):
```python
    "polygon": {"size": True},
```

In `src/tool_settings.py`, add to `TOOL_DEFAULTS` (after `"lasso"` entry):
```python
    "polygon": {"size": 1},
```

- [ ] **Step 6: Add Polygon tool registration and event handling in app.py**

In `src/app.py`:

1. Add import (line 14, extend the tools import):
   Add `PolygonTool` to the import from `src.tools`

2. Add to `self._tools` dict (after `"Lasso"` entry):
   ```python
   "Polygon": PolygonTool(),
   ```

3. Add state variable in `__init__` (near `self._lasso_points`, ~line 127):
   ```python
   self._polygon_points = []
   self._polygon_closing = False
   ```

4. In `_on_tool_change` (line 648), add reset:
   ```python
   self._polygon_points = []
   ```

5. Add click handler in `_on_canvas_click` (after the Lasso block, before the end of the method):
   ```python
   elif tool_name == "Polygon":
       if not self._polygon_points:
           self._push_undo()
       self._polygon_points.append((x, y))
   ```

6. Add drag handler in `_on_canvas_drag` (after Lasso block):
   ```python
   elif self.current_tool_name == "Polygon" and self._polygon_points:
       # Draw preview of polygon so far + line to cursor
       self.pixel_canvas.clear_overlays()
       hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
       for i in range(len(self._polygon_points) - 1):
           sx, sy = self._polygon_points[i]
           ex, ey = self._polygon_points[i + 1]
           self.pixel_canvas.draw_line_preview(sx, sy, ex, ey, hex_color)
       # Line from last point to cursor
       lx, ly = self._polygon_points[-1]
       self.pixel_canvas.draw_line_preview(lx, ly, x, y, hex_color)
   ```

7. Add release handler in `_on_canvas_release` for Enter key (bind Enter in keybindings setup):
   Add a method `_commit_polygon()`:
   ```python
   def _commit_polygon(self):
       if len(self._polygon_points) >= 2:
           layer_grid = self.timeline.current_layer()
           color = self.palette.selected_color
           self._tools["Polygon"].apply(
               layer_grid, self._polygon_points, color,
               filled=False, width=self._tool_size
           )
           self._render_canvas()
       self._polygon_points = []
       self.pixel_canvas.clear_overlays()
   ```

8. Bind Enter, Escape, and double-click for Polygon closing. In `__init__`, add:
   ```python
   self.pixel_canvas.bind("<Double-Button-1>", self._on_canvas_double_click)
   self.root.bind("<Return>", lambda e: self._commit_polygon())
   self.root.bind("<Escape>", lambda e: self._cancel_polygon())
   ```
   ```python
   def _on_canvas_double_click(self, event):
       if self.current_tool_name == "Polygon" and len(self._polygon_points) >= 2:
           self._polygon_closing = True
           self._commit_polygon()
           self._polygon_closing = False

   def _cancel_polygon(self):
       if self._polygon_points:
           self._polygon_points = []
           self.pixel_canvas.clear_overlays()
           # Undo was pushed on first click, so pop it
           if self._undo_stack:
               self._undo_stack.pop()
   ```
   And in `_on_canvas_click`, guard against the double-click duplicate:
   ```python
   elif tool_name == "Polygon":
       if self._polygon_closing:
           return
       ...
   ```

- [ ] **Step 7: Run all polygon tests + existing tests**

Run: `python -m pytest tests/test_polygon_tool.py tests/test_tool_settings.py -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add src/tools.py src/app.py src/ui/icons.py src/ui/options_bar.py src/tool_settings.py tests/test_polygon_tool.py
git commit -m "feat: add Polygon tool with outline and filled modes"
```

---

### Task 2: Rounded Rectangle Tool

**Files:**
- Modify: `src/tools.py` (add class after `PolygonTool`)
- Test: `tests/test_rounded_rect_tool.py` (create)
- Modify: `src/ui/icons.py` (add icon)
- Modify: `src/ui/options_bar.py` (add TOOL_OPTIONS entry + corner radius control)
- Modify: `src/tool_settings.py` (add defaults)
- Modify: `src/app.py` (register tool + event handlers)

- [ ] **Step 1: Write failing tests**

Create `tests/test_rounded_rect_tool.py`:

```python
"""Tests for RoundedRectTool."""
from src.pixel_data import PixelGrid
from src.tools import RoundedRectTool


def test_rounded_rect_outline():
    grid = PixelGrid(20, 20)
    tool = RoundedRectTool()
    tool.apply(grid, 2, 2, 17, 12, (255, 0, 0, 255), radius=3, filled=False)
    # Straight top edge (between corners) should be drawn
    assert grid.get_pixel(10, 2) == (255, 0, 0, 255)
    # Center should be empty (outline)
    assert grid.get_pixel(10, 7) == (0, 0, 0, 0)


def test_rounded_rect_filled():
    grid = PixelGrid(20, 20)
    tool = RoundedRectTool()
    tool.apply(grid, 2, 2, 17, 12, (0, 255, 0, 255), radius=3, filled=True)
    # Center should be filled
    assert grid.get_pixel(10, 7) == (0, 255, 0, 255)
    # Outside should be empty
    assert grid.get_pixel(0, 0) == (0, 0, 0, 0)


def test_rounded_rect_radius_clamped():
    """Radius should be clamped to fit the rectangle."""
    grid = PixelGrid(10, 10)
    tool = RoundedRectTool()
    # 4x4 rect: max radius = (4-1)//2 = 1
    tool.apply(grid, 3, 3, 6, 6, (255, 0, 0, 255), radius=10, filled=False)
    # Should not crash; corners should still be drawn
    assert grid.get_pixel(3, 3) == (255, 0, 0, 255)


def test_rounded_rect_radius_zero_is_regular_rect():
    grid = PixelGrid(10, 10)
    tool = RoundedRectTool()
    tool.apply(grid, 2, 2, 7, 7, (255, 0, 0, 255), radius=0, filled=False)
    # Corner should be sharp (like regular rect)
    assert grid.get_pixel(2, 2) == (255, 0, 0, 255)


def test_rounded_rect_small_rect():
    """Very small rect should not crash."""
    grid = PixelGrid(10, 10)
    tool = RoundedRectTool()
    tool.apply(grid, 4, 4, 5, 5, (255, 0, 0, 255), radius=2, filled=True)
    assert grid.get_pixel(4, 4) == (255, 0, 0, 255)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_rounded_rect_tool.py -v`
Expected: FAIL — `ImportError: cannot import name 'RoundedRectTool'`

- [ ] **Step 3: Write RoundedRectTool implementation**

Add to `src/tools.py` after `PolygonTool`:

```python
class RoundedRectTool:
    """Draw rectangles with rounded corners."""

    @staticmethod
    def apply(grid, x0: int, y0: int, x1: int, y1: int, color: tuple,
              radius: int = 2, filled: bool = False, width: int = 1) -> None:
        # Normalize coordinates
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0

        w = x1 - x0
        h = y1 - y0
        # Clamp radius
        max_r = max(0, (min(w, h) - 1) // 2)
        r = min(radius, max_r)

        if r <= 0:
            # Fall back to regular rectangle
            RectTool().apply(grid, x0, y0, x1, y1, color, filled=filled, width=width)
            return

        if filled:
            _rounded_rect_filled(grid, x0, y0, x1, y1, r, color)
        else:
            _rounded_rect_outline(grid, x0, y0, x1, y1, r, color, width)


def _rounded_rect_outline(grid, x0, y0, x1, y1, r, color, width):
    """Draw rounded rectangle outline using midpoint circle for corners."""
    line = LineTool()
    # Top edge
    line.apply(grid, x0 + r, y0, x1 - r, y0, color, width=width)
    # Bottom edge
    line.apply(grid, x0 + r, y1, x1 - r, y1, color, width=width)
    # Left edge
    line.apply(grid, x0, y0 + r, x0, y1 - r, color, width=width)
    # Right edge
    line.apply(grid, x1, y0 + r, x1, y1 - r, color, width=width)
    # Corners (quarter circles)
    _quarter_circle(grid, x0 + r, y0 + r, r, color, "tl", width)
    _quarter_circle(grid, x1 - r, y0 + r, r, color, "tr", width)
    _quarter_circle(grid, x0 + r, y1 - r, r, color, "bl", width)
    _quarter_circle(grid, x1 - r, y1 - r, r, color, "br", width)


def _rounded_rect_filled(grid, x0, y0, x1, y1, r, color):
    """Fill rounded rectangle using scanlines."""
    for y in range(y0, y1 + 1):
        if y < y0 + r:
            # Top rounded region
            dy = y0 + r - y
            dx = int((r * r - dy * dy) ** 0.5 + 0.5)
            xl = x0 + r - dx
            xr = x1 - r + dx
        elif y > y1 - r:
            # Bottom rounded region
            dy = y - (y1 - r)
            dx = int((r * r - dy * dy) ** 0.5 + 0.5)
            xl = x0 + r - dx
            xr = x1 - r + dx
        else:
            # Straight middle
            xl = x0
            xr = x1
        xl = max(0, xl)
        xr = min(grid.width - 1, xr)
        for x in range(xl, xr + 1):
            if 0 <= y < grid.height:
                grid.set_pixel(x, y, color)


def _quarter_circle(grid, cx, cy, r, color, quadrant, width=1):
    """Draw a quarter circle using midpoint algorithm."""
    x, y = 0, r
    d = 1 - r
    while x <= y:
        # Map (x,y) to the correct quadrant
        if quadrant == "tl":
            points = [(-y, -x), (-x, -y)]
        elif quadrant == "tr":
            points = [(y, -x), (x, -y)]
        elif quadrant == "bl":
            points = [(-y, x), (-x, y)]
        elif quadrant == "br":
            points = [(y, x), (x, y)]
        for dx, dy in points:
            px, py = cx + dx, cy + dy
            if 0 <= px < grid.width and 0 <= py < grid.height:
                _set_thick(grid, px, py, color, width)
        if d < 0:
            d += 2 * x + 3
        else:
            d += 2 * (x - y) + 5
            y -= 1
        x += 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_rounded_rect_tool.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Register RoundedRect in toolbar, icons, options_bar, and tool_settings**

In `src/ui/icons.py`, add to `TOOL_ICON_MAP`:
```python
    "roundrect": "rounded-rect-bold.svg",
```

In `src/ui/icons.py`, add to `_PNG_FALLBACK`:
```python
    "roundrect": "RR",
```

In `src/ui/options_bar.py`, add to `TOOL_OPTIONS`:
```python
    "roundrect": {"size": True},
```

In `src/tool_settings.py`, add to `TOOL_DEFAULTS`:
```python
    "roundrect": {"size": 1, "corner_radius": 2},
```

In `src/ui/options_bar.py`, add corner radius UI controls. After the tolerance frame setup (~line 150), add:
```python
# Corner radius frame
self._radius_frame = tk.Frame(self, bg=bg)
tk.Button(self._radius_frame, text="-", width=2, bg=bg, fg=fg,
          command=lambda: self._change_radius(-1)).pack(side="left")
self._radius_var = tk.IntVar(value=2)
tk.Label(self._radius_frame, textvariable=self._radius_var,
         width=3, bg=bg, fg=fg).pack(side="left")
tk.Button(self._radius_frame, text="+", width=2, bg=bg, fg=fg,
          command=lambda: self._change_radius(1)).pack(side="left")
```

Add the `_change_radius` method:
```python
def _change_radius(self, delta):
    new = max(0, min(16, self._radius_var.get() + delta))
    self._radius_var.set(new)
    if self._on_radius_change:
        self._on_radius_change(new)
```

Update `set_tool()` to show/hide radius frame:
```python
(self._radius_frame, "corner_radius"),
```

Update `restore_settings()` to handle corner_radius:
```python
if "corner_radius" in settings:
    self._radius_var.set(settings["corner_radius"])
```

- [ ] **Step 6: Add RoundedRect tool handling in app.py**

Follow the same click-drag-release pattern as RectTool:
1. Add `RoundedRectTool` to imports and `self._tools` dict
2. Add `self._roundrect_start = None` state variable
3. Reset it in `_on_tool_change`
4. Add `self._corner_radius = 2` state variable
5. In click handler: `self._roundrect_start = (x, y)`
6. In drag handler: draw preview (reuse rect preview)
7. In release handler: apply with `self._corner_radius`
8. Add `_on_radius_change` callback wired to options_bar
9. Add `corner_radius` to `_capture_current_tool_settings` and `_apply_tool_settings`

- [ ] **Step 7: Run tests**

Run: `python -m pytest tests/test_rounded_rect_tool.py tests/test_tool_settings.py -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add src/tools.py src/app.py src/ui/icons.py src/ui/options_bar.py src/tool_settings.py tests/test_rounded_rect_tool.py
git commit -m "feat: add Rounded Rectangle tool with corner radius control"
```

---

### Task 3: Contour Fill Mode

**Files:**
- Modify: `src/tools.py` (update `FillTool.apply`)
- Test: `tests/test_contour_fill.py` (create)
- Modify: `src/ui/options_bar.py` (add fill mode toggle)
- Modify: `src/tool_settings.py` (add fill_mode to fill defaults)
- Modify: `src/app.py` (wire fill_mode)

- [ ] **Step 1: Write failing tests**

Create `tests/test_contour_fill.py`:

```python
"""Tests for Contour Fill mode."""
from src.pixel_data import PixelGrid
from src.tools import FillTool


def test_contour_fill_square():
    """Contour fill on a white region surrounded by transparent should fill only border pixels."""
    grid = PixelGrid(10, 10)
    white = (255, 255, 255, 255)
    red = (255, 0, 0, 255)
    # Fill a 5x5 block with white
    for x in range(2, 7):
        for y in range(2, 7):
            grid.set_pixel(x, y, white)
    # Contour fill from center — should only fill border pixels
    tool = FillTool()
    tool.apply(grid, 4, 4, red, contour=True)
    # Border pixels should be red
    assert grid.get_pixel(2, 2) == red
    assert grid.get_pixel(6, 2) == red
    assert grid.get_pixel(2, 6) == red
    # Interior pixels should remain white
    assert grid.get_pixel(4, 4) == white


def test_contour_fill_single_pixel():
    """Contour fill on a single pixel region should fill that pixel."""
    grid = PixelGrid(10, 10)
    white = (255, 255, 255, 255)
    red = (255, 0, 0, 255)
    grid.set_pixel(5, 5, white)
    tool = FillTool()
    tool.apply(grid, 5, 5, red, contour=True)
    assert grid.get_pixel(5, 5) == red


def test_normal_fill_unchanged():
    """Normal fill should still work as before."""
    grid = PixelGrid(10, 10)
    red = (255, 0, 0, 255)
    tool = FillTool()
    tool.apply(grid, 0, 0, red, contour=False)
    # All transparent pixels should be red
    assert grid.get_pixel(5, 5) == red
    assert grid.get_pixel(9, 9) == red


def test_contour_fill_on_transparent():
    """Contour fill on the transparent region should outline its border."""
    grid = PixelGrid(10, 10)
    white = (255, 255, 255, 255)
    blue = (0, 0, 255, 255)
    # Place a white pixel in the middle
    grid.set_pixel(5, 5, white)
    # Contour fill the transparent region from (0,0)
    tool = FillTool()
    tool.apply(grid, 0, 0, blue, contour=True)
    # Pixels adjacent to the white pixel should be blue (they're border of transparent region)
    assert grid.get_pixel(4, 5) == blue
    assert grid.get_pixel(6, 5) == blue
    # Far corner should NOT be blue (interior of transparent region)
    # Actually all edge pixels of the canvas are borders too
    assert grid.get_pixel(0, 0) == blue  # canvas edge = border
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_contour_fill.py -v`
Expected: FAIL — `TypeError: FillTool.apply() got an unexpected keyword argument 'contour'`

- [ ] **Step 3: Update FillTool with contour parameter**

In `src/tools.py`, modify `FillTool.apply()` (currently at line 150):

```python
class FillTool:
    @staticmethod
    def apply(grid, x: int, y: int, color: tuple, contour: bool = False) -> None:
        if x < 0 or x >= grid.width or y < 0 or y >= grid.height:
            return
        target = grid.get_pixel(x, y)
        if target == color:
            return

        # Flood-select the region
        region = set()
        stack = [(x, y)]
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in region:
                continue
            if cx < 0 or cx >= grid.width or cy < 0 or cy >= grid.height:
                continue
            if grid.get_pixel(cx, cy) != target:
                continue
            region.add((cx, cy))
            stack.extend([(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)])

        if contour:
            # Fill only border pixels (those with a 4-connected neighbor outside region)
            # Note: out-of-bounds neighbors (canvas edges) are automatically not in
            # the region set, so edge pixels are correctly detected as borders.
            for px, py in region:
                is_border = False
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                    nx, ny = px + dx, py + dy
                    if (nx, ny) not in region:
                        is_border = True
                        break
                if is_border:
                    grid.set_pixel(px, py, color)
        else:
            # Normal fill — fill entire region
            for px, py in region:
                grid.set_pixel(px, py, color)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_contour_fill.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Add fill_mode to tool settings and options bar**

In `src/tool_settings.py`, update fill defaults:
```python
    "fill":    {"tolerance": 32, "dither": "none", "fill_mode": "normal"},
```

In `src/ui/options_bar.py`, add to `TOOL_OPTIONS` for `"fill"`:
```python
    "fill":    {"tolerance": True, "dither": True, "fill_mode": True},
```

Add a fill mode toggle button in `OptionsBar.__init__` and wire to `_fill_mode_var`. Add to `set_tool` visibility logic. Update `restore_settings` to handle `fill_mode`.

In `src/app.py`, add `self._fill_mode = "normal"` state variable. Wire it so the fill tool call passes `contour=(self._fill_mode == "contour")`. Add to `_capture_current_tool_settings` and `_apply_tool_settings`.

- [ ] **Step 6: Run all tests**

Run: `python -m pytest tests/test_contour_fill.py tests/test_tool_settings.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/tools.py src/app.py src/ui/options_bar.py src/tool_settings.py tests/test_contour_fill.py
git commit -m "feat: add Contour Fill mode to Fill tool"
```

---

### Task 4: Move Tool

**Files:**
- Modify: `src/app.py` (add move tool handlers)
- Test: `tests/test_move_tool.py` (create)
- Modify: `src/ui/icons.py` (add icon)
- Modify: `src/ui/options_bar.py` (add TOOL_OPTIONS entry)
- Modify: `src/tool_settings.py` (add defaults)

- [ ] **Step 1: Write failing tests**

Create `tests/test_move_tool.py`:

```python
"""Tests for move tool logic (pixel shifting)."""
import numpy as np
from src.pixel_data import PixelGrid


def shift_pixels(grid: PixelGrid, dx: int, dy: int) -> PixelGrid:
    """Shift all pixels in a grid by (dx, dy), clipping at boundaries.
    This is the core algorithm the move tool will use."""
    from src.app import _shift_grid
    return _shift_grid(grid, dx, dy)


def test_shift_right():
    grid = PixelGrid(5, 5)
    grid.set_pixel(0, 0, (255, 0, 0, 255))
    result = shift_pixels(grid, 2, 0)
    assert result.get_pixel(2, 0) == (255, 0, 0, 255)
    assert result.get_pixel(0, 0) == (0, 0, 0, 0)


def test_shift_down():
    grid = PixelGrid(5, 5)
    grid.set_pixel(0, 0, (255, 0, 0, 255))
    result = shift_pixels(grid, 0, 3)
    assert result.get_pixel(0, 3) == (255, 0, 0, 255)
    assert result.get_pixel(0, 0) == (0, 0, 0, 0)


def test_shift_clips_at_boundary():
    grid = PixelGrid(5, 5)
    grid.set_pixel(4, 4, (255, 0, 0, 255))
    result = shift_pixels(grid, 2, 0)
    # Pixel moved off-canvas
    assert result.get_pixel(4, 4) == (0, 0, 0, 0)
    # No pixel at (6,4) because canvas is 5 wide


def test_shift_zero():
    grid = PixelGrid(5, 5)
    grid.set_pixel(2, 2, (255, 0, 0, 255))
    result = shift_pixels(grid, 0, 0)
    assert result.get_pixel(2, 2) == (255, 0, 0, 255)
```

- [ ] **Step 2: Write the shift function in app.py**

Add a module-level helper function in `src/app.py` (or a small utility):

```python
def _shift_grid(grid, dx: int, dy: int):
    """Return a new grid (same type) with all pixels shifted by (dx, dy).
    Works for both PixelGrid (RGBA) and IndexedPixelGrid."""
    result = grid.copy()
    # Determine the backing array attribute
    if hasattr(grid, '_indices'):
        arr = grid._indices
        new_arr = np.zeros_like(arr)
    else:
        arr = grid._pixels
        new_arr = np.zeros_like(arr)
    h, w = arr.shape[:2]

    # Compute source and destination slices
    src_x0 = max(0, -dx)
    src_x1 = min(w, w - dx)
    src_y0 = max(0, -dy)
    src_y1 = min(h, h - dy)
    dst_x0 = max(0, dx)
    dst_x1 = min(w, w + dx)
    dst_y0 = max(0, dy)
    dst_y1 = min(h, h + dy)

    if src_x0 < src_x1 and src_y0 < src_y1:
        new_arr[dst_y0:dst_y1, dst_x0:dst_x1] = arr[src_y0:src_y1, src_x0:src_x1]

    if hasattr(result, '_indices'):
        result._indices = new_arr
    else:
        result._pixels = new_arr
    return result
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_move_tool.py -v`
Expected: All 4 tests PASS

- [ ] **Step 4: Register Move tool in toolbar, icons, options_bar, and tool_settings**

In `src/ui/icons.py`, add to `TOOL_ICON_MAP` (before `"hand"`):
```python
    "move": "arrows-out-cardinal-bold.svg",
```

In `src/ui/icons.py`, add to `_PNG_FALLBACK`:
```python
    "move": "V",
```

In `src/ui/options_bar.py`, add to `TOOL_OPTIONS`:
```python
    "move":    {},
```

In `src/tool_settings.py`, add to `TOOL_DEFAULTS`:
```python
    "move":    {},
```

- [ ] **Step 5: Add Move tool event handling in app.py**

1. Add state variables:
   ```python
   self._move_start = None  # (x, y) grid position at drag start
   self._move_snapshot = None  # PixelGrid snapshot for move
   ```

2. In `_on_tool_change`, add reset:
   ```python
   self._move_start = None
   self._move_snapshot = None
   ```

3. In `_on_tool_change`, set raw callbacks for Move tool (like Hand tool):
   ```python
   if name in ("Hand", "Move"):
       ...
   ```
   Actually, Move tool should use grid-coordinate callbacks (not raw), so use the standard `_on_canvas_click`/`_on_canvas_drag`/`_on_canvas_release` handlers.

4. Click handler (in `_on_canvas_click`):
   ```python
   elif tool_name == "Move":
       self._push_undo()
       self._move_start = (x, y)
       self._move_snapshot = self.timeline.current_layer().copy()
   ```

5. Drag handler (in `_on_canvas_drag`):
   ```python
   elif self.current_tool_name == "Move" and self._move_start:
       dx = x - self._move_start[0]
       dy = y - self._move_start[1]
       shifted = _shift_grid(self._move_snapshot, dx, dy)
       layer = self.timeline.current_layer()
       layer._pixels = shifted._pixels.copy()
       self._render_canvas()
       self._update_status(f"Move: ({dx}, {dy})")
   ```

6. Release handler (in `_on_canvas_release`):
   ```python
   elif self.current_tool_name == "Move" and self._move_start:
       self._move_start = None
       self._move_snapshot = None
       self._render_canvas()
   ```

- [ ] **Step 6: Handle selection-aware move**

In the click handler, add before the plain move case:
```python
elif tool_name == "Move":
    if self._selection_pixels:
        # Cut selection to floating paste, then user drags
        self._copy_selection()
        self._delete_selection()
        self._paste_clipboard()
    else:
        self._push_undo()
        self._move_start = (x, y)
        self._move_snapshot = self.timeline.current_layer().copy()
```

- [ ] **Step 7: Run all tests**

Run: `python -m pytest tests/test_move_tool.py tests/test_tool_settings.py -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add src/app.py src/ui/icons.py src/ui/options_bar.py src/tool_settings.py tests/test_move_tool.py
git commit -m "feat: add Move tool for layer content and selection movement"
```

---

## Chunk 2: Layer Workflow (Batch B)

### Task 5: Linked Cels

**Files:**
- Modify: `src/layer.py` (add `cel_id` field, `unlink()` method)
- Modify: `src/animation.py` (update `Frame.copy()`, add `is_linked()`, auto-unlink in merge_down)
- Modify: `src/project.py` (serialize/deserialize cel_id and cel_ref deduplication)
- Modify: `src/ui/timeline.py` (link indicators, unlink context menu)
- Test: `tests/test_linked_cels.py` (create)

- [ ] **Step 1: Write failing tests**

Create `tests/test_linked_cels.py`:

```python
"""Tests for Linked Cels feature."""
from src.animation import AnimationTimeline, Frame
from src.layer import Layer
from src.pixel_data import PixelGrid


def test_layer_has_cel_id():
    layer = Layer("Test", 4, 4)
    assert hasattr(layer, 'cel_id')
    assert isinstance(layer.cel_id, str)
    assert len(layer.cel_id) > 0


def test_new_layers_have_unique_cel_ids():
    l1 = Layer("A", 4, 4)
    l2 = Layer("B", 4, 4)
    assert l1.cel_id != l2.cel_id


def test_frame_copy_linked_shares_pixels():
    frame = Frame(4, 4)
    frame.layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))
    linked = frame.copy(linked=True)
    # Same pixel data reference
    assert linked.layers[0].pixels is frame.layers[0].pixels
    assert linked.layers[0].cel_id == frame.layers[0].cel_id


def test_frame_copy_unlinked_copies_pixels():
    frame = Frame(4, 4)
    frame.layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))
    independent = frame.copy(linked=False)
    # Different pixel data reference
    assert independent.layers[0].pixels is not frame.layers[0].pixels
    assert independent.layers[0].cel_id != frame.layers[0].cel_id
    # But same content
    assert independent.layers[0].pixels.get_pixel(0, 0) == (255, 0, 0, 255)


def test_linked_edit_propagates():
    frame1 = Frame(4, 4)
    frame2 = frame1.copy(linked=True)
    # Edit in frame2 should be visible in frame1
    frame2.layers[0].pixels.set_pixel(1, 1, (0, 255, 0, 255))
    assert frame1.layers[0].pixels.get_pixel(1, 1) == (0, 255, 0, 255)


def test_unlink_creates_independence():
    frame1 = Frame(4, 4)
    frame2 = frame1.copy(linked=True)
    # Unlink frame2's layer
    frame2.layers[0].unlink()
    assert frame2.layers[0].cel_id != frame1.layers[0].cel_id
    # Edits should now be independent
    frame2.layers[0].pixels.set_pixel(2, 2, (0, 0, 255, 255))
    assert frame1.layers[0].pixels.get_pixel(2, 2) == (0, 0, 0, 0)


def test_duplicate_frame_creates_linked():
    tl = AnimationTimeline(4, 4)
    tl.current_layer().set_pixel(0, 0, (255, 0, 0, 255))
    tl.duplicate_frame(0)
    # Frame 0 and frame 1 should share pixels
    f0 = tl.get_frame_obj(0)
    f1 = tl.get_frame_obj(1)
    assert f0.layers[0].pixels is f1.layers[0].pixels
    assert f0.layers[0].cel_id == f1.layers[0].cel_id


def test_is_linked():
    tl = AnimationTimeline(4, 4)
    tl.duplicate_frame(0)
    assert tl.is_linked(0, 0) is True
    assert tl.is_linked(1, 0) is True


def test_is_linked_after_unlink():
    tl = AnimationTimeline(4, 4)
    tl.duplicate_frame(0)
    tl.get_frame_obj(1).layers[0].unlink()
    assert tl.is_linked(0, 0) is False
    assert tl.is_linked(1, 0) is False


def test_merge_down_auto_unlinks():
    """Merging down should unlink the target layer first."""
    tl = AnimationTimeline(4, 4)
    tl.current_frame_obj().add_layer("Top")
    tl.duplicate_frame(0)  # Both frames now linked
    f0 = tl.get_frame_obj(0)
    f1 = tl.get_frame_obj(1)
    # Merge down in frame 0 only
    f0.merge_down(1)
    # Frame 0's bottom layer should no longer be linked to frame 1
    assert f0.layers[0].cel_id != f1.layers[0].cel_id


def test_layer_copy_creates_new_cel_id():
    layer = Layer("Test", 4, 4)
    layer.pixels.set_pixel(0, 0, (255, 0, 0, 255))
    copied = layer.copy()
    assert copied.cel_id != layer.cel_id
    assert copied.pixels is not layer.pixels
    assert copied.pixels.get_pixel(0, 0) == (255, 0, 0, 255)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_linked_cels.py -v`
Expected: FAIL — `AttributeError: 'Layer' object has no attribute 'cel_id'`

- [ ] **Step 3: Add cel_id to Layer**

In `src/layer.py`, add import and field:

```python
from uuid import uuid4
```

In `Layer.__init__`, add after `self.effects`:
```python
        self.cel_id: str = str(uuid4())
```

In `Layer.copy()`, add after copying all fields:
```python
        new_layer.cel_id = str(uuid4())  # Independent copy gets new ID
```

Add `unlink()` method to Layer:
```python
    def unlink(self):
        """Make this layer's pixel data independent by deep-copying."""
        self.pixels = self.pixels.copy()
        self.cel_id = str(uuid4())
```

- [ ] **Step 4: Update Frame.copy() to support linked parameter**

In `src/animation.py`, modify `Frame.copy()` (line 112):

```python
    def copy(self, linked: bool = False) -> Frame:
        new_frame = Frame(self.width, self.height, self.name,
                          color_mode=self.color_mode, palette=self._palette)
        new_layer_list = []
        for layer in self.layers:
            if linked:
                # Create independent shell, then share pixel data
                new_layer = layer.copy()  # deep copy handles indexed/rgba correctly
                new_layer.pixels = layer.pixels  # Override with shared reference
                new_layer.cel_id = layer.cel_id  # Same ID = linked
            else:
                new_layer = layer.copy()  # independent copy with new cel_id
            new_layer_list.append(new_layer)
        new_frame.layers = new_layer_list
        new_frame.active_layer_index = self.active_layer_index
        new_frame.duration_ms = self.duration_ms
        return new_frame
```

- [ ] **Step 5: Update duplicate_frame() to use linked=True**

In `src/animation.py`, `AnimationTimeline.duplicate_frame()` (line 243) — keep existing `index` parameter:

```python
    def duplicate_frame(self, index: int) -> None:
        if 0 <= index < len(self._frames):
            copy = self._frames[index].copy(linked=True)
            self._frames.insert(index + 1, copy)
```

- [ ] **Step 6: Add is_linked() to AnimationTimeline**

```python
    def is_linked(self, frame_idx: int, layer_idx: int) -> bool:
        """Check if a cel is linked (shared) with any other frame."""
        target_id = self._frames[frame_idx].layers[layer_idx].cel_id
        for i, frame in enumerate(self._frames):
            if i == frame_idx:
                continue
            if layer_idx < len(frame.layers):
                if frame.layers[layer_idx].cel_id == target_id:
                    return True
        return False
```

- [ ] **Step 7: Add auto-unlink to merge_down**

In `Frame.merge_down()`, at the start of the method (before the merge logic, parameter is `index`):
```python
        # Auto-unlink the below layer to prevent cross-frame propagation
        below = self.layers[index - 1]
        if hasattr(below, 'unlink'):
            below.unlink()
```

In `AnimationTimeline.merge_down_in_all()`, add the same auto-unlink before each frame's merge.

- [ ] **Step 8: Run tests**

Run: `python -m pytest tests/test_linked_cels.py -v`
Expected: All 12 tests PASS

- [ ] **Step 9: Update existing test_animation.py test**

The existing `test_duplicate_frame` test asserts independence. Since `duplicate_frame()` now creates linked frames, update it:
```python
def test_duplicate_frame(self):
    ...
    # After duplicate, frames are linked
    timeline.get_frame_obj(1).layers[0].pixels.set_pixel(0, 0, (0, 0, 0, 0))
    # Frame 0 should also be affected (linked)
    assert timeline.get_frame(0).get_pixel(0, 0) == (0, 0, 0, 0)
```

Or add a new test for the linked behavior and adjust the existing test to use `unlink()` first.

- [ ] **Step 10: Update project serialization**

In `src/project.py`:

On save — track which cel_ids have been serialized:
```python
    serialized_cels = {}  # cel_id -> True (already written)
    for frame in frames_data:
        for layer in frame["layers"]:
            cel_id = layer.get("cel_id")
            if cel_id in serialized_cels:
                # Replace pixel data with reference
                layer.pop("pixels", None)
                layer["cel_ref"] = cel_id
            else:
                serialized_cels[cel_id] = True
```

On load — track loaded pixel data for linking:
```python
    cel_cache = {}  # cel_id -> PixelGrid reference
    for frame in loaded_frames:
        for layer in frame.layers:
            if "cel_ref" in layer_data:
                layer.pixels = cel_cache[layer_data["cel_ref"]]
                layer.cel_id = layer_data["cel_ref"]
            else:
                cel_cache[layer.cel_id] = layer.pixels
```

- [ ] **Step 11: Run all tests**

Run: `python -m pytest tests/test_linked_cels.py tests/test_animation.py tests/test_tool_settings.py -v`
Expected: All tests PASS

- [ ] **Step 12: Commit**

```bash
git add src/layer.py src/animation.py src/project.py tests/test_linked_cels.py tests/test_animation.py
git commit -m "feat: add Linked Cels — duplicated frames share pixel data"
```

---

### Task 6: Clipping Masks

**Files:**
- Modify: `src/layer.py` (add `clipping` field, update `flatten_layers()`)
- Modify: `src/project.py` (serialize/deserialize clipping)
- Modify: `src/ui/timeline.py` (clip-to-below context menu, visual indicator)
- Test: `tests/test_clipping_mask.py` (create)

- [ ] **Step 1: Write failing tests**

Create `tests/test_clipping_mask.py`:

```python
"""Tests for Clipping Masks."""
import numpy as np
from src.pixel_data import PixelGrid
from src.layer import Layer, flatten_layers


def test_layer_has_clipping_field():
    layer = Layer("Test", 4, 4)
    assert hasattr(layer, 'clipping')
    assert layer.clipping is False


def test_clipping_mask_hides_outside_base():
    """Clipped layer should only be visible within base layer's opaque pixels."""
    base = Layer("Base", 4, 4)
    # Base has a 2x2 opaque square in top-left
    base.pixels.set_pixel(0, 0, (255, 0, 0, 255))
    base.pixels.set_pixel(1, 0, (255, 0, 0, 255))
    base.pixels.set_pixel(0, 1, (255, 0, 0, 255))
    base.pixels.set_pixel(1, 1, (255, 0, 0, 255))

    clip = Layer("Clip", 4, 4)
    clip.clipping = True
    # Clip layer is fully blue
    for x in range(4):
        for y in range(4):
            clip.pixels.set_pixel(x, y, (0, 0, 255, 255))

    result = flatten_layers([base, clip], 4, 4)
    # Where base is opaque, clip should be visible (blue over red)
    p00 = result.get_pixel(0, 0)
    assert p00 == (0, 0, 255, 255)  # blue (clip on top)
    # Where base is transparent, clip should NOT be visible
    p22 = result.get_pixel(2, 2)
    assert p22 == (0, 0, 0, 0)  # transparent


def test_clipping_bottom_layer_treated_as_normal():
    """Bottom-most layer with clipping=True should be treated as normal."""
    layer = Layer("Bottom", 4, 4)
    layer.clipping = True
    layer.pixels.set_pixel(0, 0, (255, 0, 0, 255))

    result = flatten_layers([layer], 4, 4)
    assert result.get_pixel(0, 0) == (255, 0, 0, 255)


def test_multiple_clipped_layers():
    """Multiple consecutive clipped layers all clip to the same base."""
    base = Layer("Base", 4, 4)
    base.pixels.set_pixel(0, 0, (255, 0, 0, 255))

    clip1 = Layer("Clip1", 4, 4)
    clip1.clipping = True
    clip1.pixels.set_pixel(0, 0, (0, 255, 0, 128))

    clip2 = Layer("Clip2", 4, 4)
    clip2.clipping = True
    clip2.pixels.set_pixel(0, 0, (0, 0, 255, 128))

    result = flatten_layers([base, clip1, clip2], 4, 4)
    # (0,0) should have content (base + clip1 + clip2 composited)
    p = result.get_pixel(0, 0)
    assert p[3] > 0  # Not transparent
    # (2,2) should be transparent (no base content there)
    assert result.get_pixel(2, 2) == (0, 0, 0, 0)


def test_clipping_with_half_opacity_base():
    """Clip base with 50% opacity — clipped layer should use base's own alpha."""
    base = Layer("Base", 4, 4)
    base.opacity = 0.5
    base.pixels.set_pixel(0, 0, (255, 0, 0, 255))

    clip = Layer("Clip", 4, 4)
    clip.clipping = True
    clip.pixels.set_pixel(0, 0, (0, 0, 255, 255))
    # Clip across entire canvas
    clip.pixels.set_pixel(2, 2, (0, 0, 255, 255))

    result = flatten_layers([base, clip], 4, 4)
    # (0,0): base has alpha, so clip is visible (but masked to 50% base alpha)
    assert result.get_pixel(0, 0)[3] > 0
    # (2,2): base has no pixel there, so clip should be invisible
    assert result.get_pixel(2, 2) == (0, 0, 0, 0)


def test_layer_copy_preserves_clipping():
    layer = Layer("Test", 4, 4)
    layer.clipping = True
    copied = layer.copy()
    assert copied.clipping is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_clipping_mask.py -v`
Expected: FAIL — `AttributeError: 'Layer' object has no attribute 'clipping'`

- [ ] **Step 3: Add clipping field to Layer**

In `src/layer.py`, `Layer.__init__`, add after `self.effects`:
```python
        self.clipping: bool = False
```

In `Layer.copy()`, add:
```python
        new_layer.clipping = self.clipping
```

- [ ] **Step 4: Update flatten_layers() with clipping logic**

In `src/layer.py`, modify `flatten_layers()`. The key change is tracking `base_alpha` and applying it to clipped layers.

The existing `flatten_layers()` uses a `while i < len(layers)` loop with a stack for groups. The stack tuple currently has 5 elements. We add `base_alpha` as a 6th element to the stack, and track it in the main scope.

**Changes to `flatten_layers()` in `src/layer.py`:**

1. Add `base_alpha = None` variable after `skip_depth = -1` (line 119):
```python
    base_alpha = None  # clip-base layer's own alpha (float32 array, 0.0-1.0)
```

2. Update stack tuple to 6 elements. Change the `stack.append(...)` at line 149 to:
```python
            stack.append((current, layer.blend_mode, layer.opacity, layer.visible, depth, base_alpha))
            base_alpha = None  # Reset for new group scope
```

3. Update all stack pop unpacking. At line 128, change to:
```python
            group_base, group_mode, group_opacity, group_visible, group_depth, saved_base_alpha = stack.pop()
```
And after the group compositing, restore base_alpha:
```python
            base_alpha = saved_base_alpha
```

4. At lines 183-186 (remaining groups pop), change to:
```python
        group_base, group_mode, group_opacity, group_visible, group_depth, _ = stack.pop()
```

5. After building `layer_img` (after line 176, before compositing at line 178), add clipping logic:
```python
        # Clipping mask: multiply layer alpha by base layer's own alpha
        if getattr(layer, 'clipping', False) and base_alpha is not None:
            arr = np.array(layer_img, dtype=np.float32)
            arr[:, :, 3] *= base_alpha
            layer_img = Image.fromarray(arr.astype(np.uint8), "RGBA")
        else:
            # Non-clipping layer becomes the new clip base.
            # Capture its own alpha (after opacity) BEFORE compositing with canvas.
            clip_arr = np.array(layer_img, dtype=np.uint8)
            base_alpha = clip_arr[:, :, 3].astype(np.float32) / 255.0
```

6. The compositing line (`current = _composite_one(...)`) remains unchanged after this block.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_clipping_mask.py -v`
Expected: All 6 tests PASS

- [ ] **Step 6: Update Layer.copy() and serialization**

In `src/project.py`, on save — add `"clipping"` field to layer data:
```python
layer_data["clipping"] = layer.clipping
```

On load — read clipping field:
```python
layer.clipping = layer_data.get("clipping", False)
```

- [ ] **Step 7: Add UI for clipping toggle**

In `src/ui/timeline.py`, add to the layer right-click context menu:
```python
menu.add_command(label="Clip to Below", command=lambda: self._toggle_clipping(layer_idx))
```

```python
def _toggle_clipping(self, layer_idx):
    frame = self._timeline.current_frame_obj()
    if layer_idx == 0:
        # Can't clip bottom layer
        return
    layer = frame.layers[layer_idx]
    layer.clipping = not layer.clipping
    self._refresh()
    if self._on_change:
        self._on_change()
```

Add visual indicator for clipped layers (indent or arrow prefix in label).

- [ ] **Step 8: Run all tests**

Run: `python -m pytest tests/test_clipping_mask.py tests/test_linked_cels.py tests/test_animation.py -v`
Expected: All tests PASS

- [ ] **Step 9: Commit**

```bash
git add src/layer.py src/project.py src/ui/timeline.py tests/test_clipping_mask.py
git commit -m "feat: add Clipping Masks — layers clip to the shape below"
```

---

### Task 7: Final Integration and Full Test Suite

**Files:**
- All modified files
- Run full test suite

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS (except pre-existing failures like PSD import)

- [ ] **Step 2: Verify no regressions in existing tool settings tests**

Run: `python -m pytest tests/test_tool_settings.py -v`
Expected: All tests PASS (tool_settings.py was updated with new tool defaults)

- [ ] **Step 3: Cross-feature verification**

Verify that new tools work with per-tool settings:
- Switch to Polygon, change size, switch away, switch back — size should be remembered
- Switch to RoundedRect, change corner radius, switch away, switch back — radius should be remembered
- Switch to Fill, change to contour mode, switch away, switch back — mode should be remembered

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: competitive features batch — polygon, rounded rect, contour fill, move, linked cels, clipping masks"
```
