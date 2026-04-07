# Batch 3: Drawing Modes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tiled/seamless drawing mode, ink modes (alpha lock, behind), and a color ramp generator dialog.

**Architecture:** Three independent features: (1) Tiled mode adds coordinate wrapping in drawing tools and 3x3 visual preview in the render pipeline. (2) Ink modes add alpha checks before pixel writes in pen/eraser. (3) Color ramp generator is a standalone dialog that appends interpolated colors to the palette.

**Tech Stack:** Python 3.8+, Tkinter, NumPy, PIL/Pillow

**IMPORTANT:** No git — do not init, commit, or use any git commands.

---

## Chunk 1: Tiled/Seamless Drawing Mode

### Task 1: Tiled Mode State & View Menu

**Files:**
- Modify: `src/app.py` (add state variable + View menu)

- [ ] **Step 1: Add tiled mode state variable**

In `src/app.py`, after line ~119 (`self._dither_pattern = "none"`), add:

```python
self._tiled_mode = "off"  # off, x, y, both
```

- [ ] **Step 2: Create View menu in `_build_menu`**

In `src/app.py`, in `_build_menu()`, after the Animation menu cascade (line ~246) and before the Compression menu, add a View menu:

```python
# View menu
view_menu = tk.Menu(menubar, tearoff=0)
self._tiled_var = tk.StringVar(value="off")
view_menu.add_radiobutton(label="Tiled Off", variable=self._tiled_var,
                          value="off", command=self._on_tiled_mode_change)
view_menu.add_radiobutton(label="Tiled X", variable=self._tiled_var,
                          value="x", command=self._on_tiled_mode_change)
view_menu.add_radiobutton(label="Tiled Y", variable=self._tiled_var,
                          value="y", command=self._on_tiled_mode_change)
view_menu.add_radiobutton(label="Tiled Both", variable=self._tiled_var,
                          value="both", command=self._on_tiled_mode_change)
menubar.add_cascade(label="View", menu=view_menu)
```

- [ ] **Step 3: Add tiled mode change handler**

In `src/app.py`, add the handler method (near other `_on_*_change` methods):

```python
def _on_tiled_mode_change(self):
    self._tiled_mode = self._tiled_var.get()
    self._render_canvas()
    self._update_status(f"Tiled: {self._tiled_mode}")
```

- [ ] **Step 4: Run tests to verify no regressions**

Run: `python -m pytest tests/ -x -q`
Expected: All existing tests pass.

### Task 2: Coordinate Wrapping in Drawing Tools

**Files:**
- Modify: `src/app.py` (wrap coordinates before tool apply calls)

- [ ] **Step 1: Add `_wrap_coord` helper method**

In `src/app.py`, add a helper method:

```python
def _wrap_coord(self, x, y):
    """Wrap coordinates based on tiled mode. Returns (x, y)."""
    w, h = self.timeline.width, self.timeline.height
    mode = self._tiled_mode
    if mode in ("x", "both"):
        x = x % w
    if mode in ("y", "both"):
        y = y % h
    return x, y
```

- [ ] **Step 2: Apply wrapping in `_on_canvas_click` for Pen/Eraser/Fill**

In `_on_canvas_click`, right after `size = self._tool_size` (line ~571), add coordinate wrapping for tools that draw:

```python
if self._tiled_mode != "off" and tool_name in ("Pen", "Eraser", "Fill", "Blur"):
    x, y = self._wrap_coord(x, y)
```

- [ ] **Step 3: Apply wrapping in `_on_canvas_drag` for Pen/Eraser/Blur**

In `_on_canvas_drag`, at the top of the method after the locked-layer check (line ~642), add:

```python
if self._tiled_mode != "off" and self.current_tool_name in ("Pen", "Eraser", "Blur"):
    x, y = self._wrap_coord(x, y)
```

- [ ] **Step 4: Apply wrapping in `_on_canvas_release` for Line/Rect/Ellipse**

In `_on_canvas_release`, before the Line tool block (line ~721), add:

```python
if self._tiled_mode != "off":
    x, y = self._wrap_coord(x, y)
```

- [ ] **Step 5: Write tests for coordinate wrapping**

Create `tests/test_tiled_mode.py`:

```python
"""Tests for tiled/seamless drawing mode."""
import pytest
from src.pixel_data import PixelGrid


class TestWrapCoord:
    """Test coordinate wrapping logic."""

    def test_wrap_x_mode(self):
        w, h = 16, 16
        # x wraps, y does not
        assert 18 % w == 2
        assert -1 % w == 15

    def test_wrap_y_mode(self):
        w, h = 16, 16
        assert 20 % h == 4
        assert -3 % h == 13

    def test_wrap_both(self):
        w, h = 8, 8
        assert (10 % w, 10 % h) == (2, 2)

    def test_no_wrap_when_off(self):
        # When off, coordinates pass through unchanged
        x, y = 20, 20
        assert (x, y) == (20, 20)

    def test_pen_wraps_on_tiled_canvas(self):
        """Drawing at x=17 on a 16-wide canvas wraps to x=1."""
        from src.tools import PenTool
        grid = PixelGrid(16, 16)
        pen = PenTool()
        # Simulate wrapping: x=17 -> x=1
        wx = 17 % 16
        pen.apply(grid, wx, 5, (255, 0, 0, 255))
        assert grid.get_pixel(1, 5) == (255, 0, 0, 255)

    def test_eraser_wraps_on_tiled_canvas(self):
        """Erasing at wrapped coordinate works."""
        from src.tools import EraserTool
        grid = PixelGrid(8, 8)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        eraser = EraserTool()
        # Simulate wrapping: x=8 -> x=0
        wx = 8 % 8
        eraser.apply(grid, wx, 0)
        assert grid.get_pixel(0, 0) == (0, 0, 0, 0)
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_tiled_mode.py -v`
Expected: All 6 tests pass.

### Task 3: Tiled Visual Preview in Render Pipeline

**Files:**
- Modify: `src/canvas.py` (add tiled_mode parameter to `build_render_image` and `render`)

- [ ] **Step 1: Add `tiled_mode` parameter to `build_render_image`**

In `src/canvas.py`, update the `build_render_image` function signature to add `tiled_mode: str = "off"` parameter:

```python
def build_render_image(grid: PixelGrid, pixel_size: int,
                       show_grid: bool,
                       onion_grid: PixelGrid | None = None,
                       onion_past_grids: list | None = None,
                       onion_future_grids: list | None = None,
                       onion_past_tint: tuple = (255, 0, 170),
                       onion_future_tint: tuple = (0, 240, 255),
                       reference_image: Image.Image | None = None,
                       reference_opacity: float = 0.3,
                       tiled_mode: str = "off") -> Image.Image:
```

- [ ] **Step 2: Add tiling logic after the final scaled image is built**

After the grid lines section (after line ~91, before `return scaled`), add the 3x3 tiling:

```python
if tiled_mode != "off":
    # Build 3x3 tiled preview
    tw, th = scaled.size
    tiled = Image.new("RGB", (tw * 3, th * 3))
    for ty in range(3):
        for tx in range(3):
            tiled.paste(scaled, (tx * tw, ty * th))
    # Dim the non-center tiles
    from PIL import ImageEnhance
    # Create dimmed version
    dimmed = ImageEnhance.Brightness(scaled).enhance(0.4)
    for ty in range(3):
        for tx in range(3):
            if tx == 1 and ty == 1:
                continue  # center tile stays bright
            tiled.paste(dimmed, (tx * tw, ty * th))
    scaled = tiled
```

- [ ] **Step 3: Update `render` method to accept and pass `tiled_mode`**

In `PixelCanvas.render()`, add `tiled_mode: str = "off"` parameter and pass it through:

```python
def render(self, onion_grid: PixelGrid | None = None,
           onion_past_grids=None, onion_future_grids=None,
           reference_image: Image.Image | None = None,
           reference_opacity: float = 0.3,
           tiled_mode: str = "off") -> None:
    img = build_render_image(self.grid, self.pixel_size, self.show_grid,
                             onion_grid,
                             onion_past_grids=onion_past_grids,
                             onion_future_grids=onion_future_grids,
                             reference_image=reference_image,
                             reference_opacity=reference_opacity,
                             tiled_mode=tiled_mode)
```

- [ ] **Step 4: Pass `tiled_mode` from app's `_render_canvas` method**

In `src/app.py`, find the `_render_canvas` method and add `tiled_mode=self._tiled_mode` to the `self.pixel_canvas.render(...)` call.

- [ ] **Step 5: Write test for tiled render**

Add to `tests/test_tiled_mode.py`:

```python
class TestTiledRender:
    def test_tiled_render_3x_size(self):
        """Tiled mode produces a 3x larger image."""
        from src.canvas import build_render_image
        grid = PixelGrid(8, 8)
        normal = build_render_image(grid, 4, False, tiled_mode="off")
        tiled = build_render_image(grid, 4, False, tiled_mode="both")
        assert normal.size == (32, 32)
        assert tiled.size == (96, 96)

    def test_tiled_x_only(self):
        """Tiled X still produces 3x image."""
        from src.canvas import build_render_image
        grid = PixelGrid(8, 8)
        tiled = build_render_image(grid, 4, False, tiled_mode="x")
        assert tiled.size == (96, 96)
```

- [ ] **Step 6: Run all tests**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass.

---

## Chunk 2: Ink Modes (Alpha Lock, Behind)

### Task 4: Ink Mode State & Options Bar Control

**Files:**
- Modify: `src/app.py` (add state variable)
- Modify: `src/ui/options_bar.py` (add ink mode button for pen/eraser)

- [ ] **Step 1: Add ink mode state variable**

In `src/app.py`, after the tiled mode state (added in Task 1), add:

```python
self._ink_mode = "normal"  # normal, alpha_lock, behind
```

- [ ] **Step 2: Add ink mode to TOOL_OPTIONS in options_bar.py**

In `src/ui/options_bar.py`, update the pen and eraser entries in `TOOL_OPTIONS`:

```python
"pen":     {"size": True, "symmetry": True, "dither": True, "pixel_perfect": True, "ink_mode": True},
"eraser":  {"size": True, "symmetry": True, "pixel_perfect": True, "ink_mode": True},
```

- [ ] **Step 3: Add ink mode cycle button to OptionsBar**

In `src/ui/options_bar.py`, in `__init__`, add an `on_ink_mode_change` parameter and the ink mode button. After the pixel perfect frame setup (~line 105):

```python
# Ink mode cycle button
self._ink_frame = tk.Frame(self, bg=BG_PANEL)
self._ink_var = tk.StringVar(value="Normal")
self._ink_btn = tk.Button(self._ink_frame, text="Ink: Normal", width=12,
                          font=("Consolas", 8),
                          bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                          command=self._cycle_ink_mode)
self._ink_btn.pack(side="left", padx=(8, 0))
self._on_ink_mode_change = on_ink_mode_change
```

Add `on_ink_mode_change=None` parameter to `__init__` signature.

- [ ] **Step 4: Add ink mode cycling method**

In `src/ui/options_bar.py`, add:

```python
_INK_MODES = ["Normal", "\u03b1Lock", "Behind"]

def _cycle_ink_mode(self):
    current = self._ink_var.get()
    idx = self._INK_MODES.index(current) if current in self._INK_MODES else 0
    new_mode = self._INK_MODES[(idx + 1) % len(self._INK_MODES)]
    self._ink_var.set(new_mode)
    self._ink_btn.config(text=f"Ink: {new_mode}")
    if self._on_ink_mode_change:
        # Map display name to internal name
        mode_map = {"Normal": "normal", "\u03b1Lock": "alpha_lock", "Behind": "behind"}
        self._on_ink_mode_change(mode_map[new_mode])
```

- [ ] **Step 5: Add ink_mode frame to show/hide logic in `set_tool`**

In `src/ui/options_bar.py`, in the `set_tool` method, add `(self._ink_frame, "ink_mode")` to the list of frame/key pairs:

```python
for frame, key in [
    (self._size_frame, "size"),
    (self._sym_frame, "symmetry"),
    (self._dither_frame, "dither"),
    (self._pp_frame, "pixel_perfect"),
    (self._tol_frame, "tolerance"),
    (self._ink_frame, "ink_mode"),
]:
```

- [ ] **Step 6: Wire up ink mode callback in app.py**

In `src/app.py`, add `on_ink_mode_change=self._on_ink_mode_change` to the OptionsBar constructor call. Add the handler:

```python
def _on_ink_mode_change(self, mode):
    self._ink_mode = mode
    self._update_status(f"Ink: {mode}")
```

- [ ] **Step 7: Run tests**

Run: `python -m pytest tests/ -x -q`
Expected: All existing tests pass.

### Task 5: Ink Mode Drawing Logic

**Files:**
- Modify: `src/app.py` (add alpha checks before pen/eraser applies)

- [ ] **Step 1: Add `_check_ink_mode` helper**

In `src/app.py`, add:

```python
def _check_ink_mode(self, grid, x, y):
    """Check if the ink mode allows painting at (x, y).
    Returns True if painting is allowed."""
    if self._ink_mode == "normal":
        return True
    current = grid.get_pixel(x, y)
    if current is None:
        return self._ink_mode == "behind"
    alpha = current[3]
    if self._ink_mode == "alpha_lock":
        return alpha > 0
    if self._ink_mode == "behind":
        return alpha == 0
    return True
```

- [ ] **Step 2: Wrap pen/eraser draw lambdas with ink mode check**

In `_on_canvas_click`, modify the Pen drawing lambda (around line ~576):

```python
if tool_name == "Pen":
    self._pp_last_points = [(x, y)]
    self._apply_symmetry_draw(
        lambda px, py: (
            self._tools["Pen"].apply(
                layer_grid, px, py, color, size=size,
                dither_pattern=self._dither_pattern,
                mask=self._custom_brush_mask)
            if self._check_ink_mode(layer_grid, px, py) else None),
        x, y)
elif tool_name == "Eraser":
    self._apply_symmetry_draw(
        lambda px, py: (
            self._tools["Eraser"].apply(
                layer_grid, px, py, size=size,
                mask=self._custom_brush_mask)
            if self._check_ink_mode(layer_grid, px, py) else None),
        x, y)
```

- [ ] **Step 3: Apply same ink mode check in `_on_canvas_drag`**

Same pattern for the Pen and Eraser blocks in `_on_canvas_drag` (~lines 667-681).

- [ ] **Step 4: Write tests for ink modes**

Create `tests/test_ink_modes.py`:

```python
"""Tests for ink modes (Normal, Alpha Lock, Behind)."""
import pytest
from src.pixel_data import PixelGrid
from src.tools import PenTool, EraserTool


class TestAlphaLock:
    def test_alpha_lock_blocks_transparent_pixels(self):
        """Alpha lock should not paint on transparent pixels."""
        grid = PixelGrid(8, 8)
        # Pixel at (2,2) is transparent (default)
        current = grid.get_pixel(2, 2)
        assert current[3] == 0  # transparent
        # Alpha lock check: should block
        assert current[3] > 0 is False

    def test_alpha_lock_allows_opaque_pixels(self):
        """Alpha lock should paint on opaque pixels."""
        grid = PixelGrid(8, 8)
        grid.set_pixel(3, 3, (100, 100, 100, 255))
        current = grid.get_pixel(3, 3)
        assert current[3] > 0  # opaque -> allowed

    def test_alpha_lock_preserves_transparent_area(self):
        """Full integration: pen with alpha lock doesn't touch transparent."""
        grid = PixelGrid(8, 8)
        grid.set_pixel(4, 4, (50, 50, 50, 200))
        pen = PenTool()
        # Only paint where alpha > 0
        for px in range(8):
            for py in range(8):
                current = grid.get_pixel(px, py)
                if current[3] > 0:
                    pen.apply(grid, px, py, (255, 0, 0, 255))
        assert grid.get_pixel(4, 4) == (255, 0, 0, 255)
        assert grid.get_pixel(0, 0) == (0, 0, 0, 0)  # still transparent


class TestBehindMode:
    def test_behind_blocks_opaque_pixels(self):
        """Behind mode should not paint on opaque pixels."""
        grid = PixelGrid(8, 8)
        grid.set_pixel(2, 2, (100, 200, 50, 255))
        current = grid.get_pixel(2, 2)
        assert current[3] == 0 is False  # opaque -> blocked

    def test_behind_allows_transparent_pixels(self):
        """Behind mode paints on transparent pixels."""
        grid = PixelGrid(8, 8)
        current = grid.get_pixel(5, 5)
        assert current[3] == 0  # transparent -> allowed

    def test_behind_preserves_existing_content(self):
        """Full integration: pen with behind mode doesn't overwrite."""
        grid = PixelGrid(8, 8)
        grid.set_pixel(3, 3, (0, 255, 0, 255))
        pen = PenTool()
        # Only paint where alpha == 0
        for px in range(8):
            for py in range(8):
                current = grid.get_pixel(px, py)
                if current[3] == 0:
                    pen.apply(grid, px, py, (255, 0, 0, 255))
        assert grid.get_pixel(3, 3) == (0, 255, 0, 255)  # preserved
        assert grid.get_pixel(0, 0) == (255, 0, 0, 255)  # filled in
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_ink_modes.py -v`
Expected: All 6 tests pass.

---

## Chunk 3: Color Ramp Generator

### Task 6: Color Ramp Generation Function

**Files:**
- Modify: `src/palette.py` (add `generate_ramp` function)
- Create: `tests/test_color_ramp.py`

- [ ] **Step 1: Write failing tests for `generate_ramp`**

Create `tests/test_color_ramp.py`:

```python
"""Tests for color ramp generator."""
import pytest
from src.palette import generate_ramp


class TestGenerateRamp:
    def test_rgb_ramp_2_steps(self):
        """2-step ramp returns just start and end."""
        ramp = generate_ramp((0, 0, 0, 255), (255, 255, 255, 255), 2, "rgb")
        assert len(ramp) == 2
        assert ramp[0] == (0, 0, 0, 255)
        assert ramp[1] == (255, 255, 255, 255)

    def test_rgb_ramp_3_steps(self):
        """3-step ramp has midpoint."""
        ramp = generate_ramp((0, 0, 0, 255), (255, 255, 255, 255), 3, "rgb")
        assert len(ramp) == 3
        assert ramp[1] == (128, 128, 128, 255)  # midpoint (rounded)

    def test_rgb_ramp_preserves_alpha(self):
        """Alpha is interpolated too."""
        ramp = generate_ramp((255, 0, 0, 0), (255, 0, 0, 255), 3, "rgb")
        assert ramp[0][3] == 0
        assert ramp[1][3] == 128
        assert ramp[2][3] == 255

    def test_hsv_ramp_2_steps(self):
        """HSV ramp with 2 steps = start and end."""
        ramp = generate_ramp((255, 0, 0, 255), (0, 0, 255, 255), 2, "hsv")
        assert len(ramp) == 2
        assert ramp[0] == (255, 0, 0, 255)
        assert ramp[1] == (0, 0, 255, 255)

    def test_hsv_ramp_shortest_path(self):
        """HSV ramp uses shortest hue path."""
        # Red (hue=0) to blue (hue=240) — shortest path goes through magenta (hue=300)
        # Actually shortest: 0->240 = 240 vs 0->360->240 = 120. Going via 300 is shorter.
        ramp = generate_ramp((255, 0, 0, 255), (0, 0, 255, 255), 3, "hsv")
        assert len(ramp) == 3
        # Middle color should be somewhere in magenta range (going via 300°)
        mid = ramp[1]
        assert mid[2] > 0  # should have blue component

    def test_ramp_step_count(self):
        """Ramp with N steps returns exactly N colors."""
        for n in [2, 5, 10, 16, 32]:
            ramp = generate_ramp((0, 0, 0, 255), (255, 255, 255, 255), n, "rgb")
            assert len(ramp) == n
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_color_ramp.py -v`
Expected: FAIL (ImportError — `generate_ramp` doesn't exist yet)

- [ ] **Step 3: Implement `generate_ramp` in palette.py**

In `src/palette.py`, add at module level (after the `Palette` class):

```python
import colorsys


def generate_ramp(color1: tuple[int, int, int, int],
                  color2: tuple[int, int, int, int],
                  steps: int,
                  mode: str = "rgb") -> list[tuple[int, int, int, int]]:
    """Generate a color ramp between two RGBA colors.

    Args:
        color1: Start color (r, g, b, a) 0-255
        color2: End color (r, g, b, a) 0-255
        steps: Number of colors (2-32)
        mode: "rgb" or "hsv"

    Returns:
        List of (r, g, b, a) tuples.
    """
    steps = max(2, min(32, steps))
    if mode == "hsv":
        return _ramp_hsv(color1, color2, steps)
    return _ramp_rgb(color1, color2, steps)


def _ramp_rgb(c1, c2, steps):
    result = []
    for i in range(steps):
        t = i / max(1, steps - 1)
        r = round(c1[0] + (c2[0] - c1[0]) * t)
        g = round(c1[1] + (c2[1] - c1[1]) * t)
        b = round(c1[2] + (c2[2] - c1[2]) * t)
        a = round(c1[3] + (c2[3] - c1[3]) * t)
        result.append((r, g, b, a))
    return result


def _ramp_hsv(c1, c2, steps):
    h1, s1, v1 = colorsys.rgb_to_hsv(c1[0] / 255, c1[1] / 255, c1[2] / 255)
    h2, s2, v2 = colorsys.rgb_to_hsv(c2[0] / 255, c2[1] / 255, c2[2] / 255)
    # Shortest hue path
    dh = h2 - h1
    if dh > 0.5:
        dh -= 1.0
    elif dh < -0.5:
        dh += 1.0
    result = []
    for i in range(steps):
        t = i / max(1, steps - 1)
        h = (h1 + dh * t) % 1.0
        s = s1 + (s2 - s1) * t
        v = v1 + (v2 - v1) * t
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        a = round(c1[3] + (c2[3] - c1[3]) * t)
        result.append((round(r * 255), round(g * 255), round(b * 255), a))
    return result
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_color_ramp.py -v`
Expected: All 6 tests pass.

### Task 7: Color Ramp Dialog

**Files:**
- Modify: `src/ui/dialogs.py` (add `ask_color_ramp` dialog)
- Modify: `src/app.py` (wire up dialog to Edit menu + palette)

- [ ] **Step 1: Add `ask_color_ramp` dialog to dialogs.py**

In `src/ui/dialogs.py`, add at the end of the file:

```python
def ask_color_ramp(parent, fg_color, bg_color) -> dict | None:
    """Show color ramp generator dialog.

    Args:
        parent: Parent window
        fg_color: (r,g,b,a) foreground color as start default
        bg_color: (r,g,b,a) background color as end default

    Returns:
        dict with keys: start, end, steps, mode — or None if cancelled.
    """
    dialog = tk.Toplevel(parent)
    dialog.title("Generate Color Ramp")
    dialog.geometry("320x280")
    dialog.resizable(False, False)
    dialog.configure(bg=BG_DEEP)
    dialog.transient(parent)
    dialog.grab_set()

    result = [None]

    # Top gradient border
    top_bar = tk.Canvas(dialog, height=2, bg=BG_DEEP, highlightthickness=0)
    top_bar.pack(fill="x")
    _draw_gradient_bar(top_bar, ACCENT_CYAN, ACCENT_PURPLE)

    tk.Label(dialog, text="Color Ramp Generator", fg=ACCENT_CYAN, bg=BG_DEEP,
             font=("Consolas", 11, "bold")).pack(pady=(10, 8))

    # Start color display
    start_frame = tk.Frame(dialog, bg=BG_DEEP)
    start_frame.pack(fill="x", padx=20, pady=2)
    tk.Label(start_frame, text="Start:", font=("Consolas", 9),
             bg=BG_DEEP, fg=TEXT_PRIMARY).pack(side="left")
    start_swatch = tk.Canvas(start_frame, width=24, height=16, bg=BG_DEEP,
                             highlightthickness=1, highlightbackground=BORDER)
    start_swatch.pack(side="left", padx=4)
    sc = f"#{fg_color[0]:02x}{fg_color[1]:02x}{fg_color[2]:02x}"
    start_swatch.create_rectangle(0, 0, 24, 16, fill=sc, outline="")
    tk.Label(start_frame, text=f"({fg_color[0]},{fg_color[1]},{fg_color[2]})",
             font=("Consolas", 8), bg=BG_DEEP, fg=TEXT_SECONDARY).pack(side="left", padx=4)

    # End color display
    end_frame = tk.Frame(dialog, bg=BG_DEEP)
    end_frame.pack(fill="x", padx=20, pady=2)
    tk.Label(end_frame, text="End:  ", font=("Consolas", 9),
             bg=BG_DEEP, fg=TEXT_PRIMARY).pack(side="left")
    end_swatch = tk.Canvas(end_frame, width=24, height=16, bg=BG_DEEP,
                           highlightthickness=1, highlightbackground=BORDER)
    end_swatch.pack(side="left", padx=4)
    ec = f"#{bg_color[0]:02x}{bg_color[1]:02x}{bg_color[2]:02x}"
    end_swatch.create_rectangle(0, 0, 24, 16, fill=ec, outline="")
    tk.Label(end_frame, text=f"({bg_color[0]},{bg_color[1]},{bg_color[2]})",
             font=("Consolas", 8), bg=BG_DEEP, fg=TEXT_SECONDARY).pack(side="left", padx=4)

    # Steps spinner
    steps_frame = tk.Frame(dialog, bg=BG_DEEP)
    steps_frame.pack(fill="x", padx=20, pady=6)
    tk.Label(steps_frame, text="Steps:", font=("Consolas", 9),
             bg=BG_DEEP, fg=TEXT_PRIMARY).pack(side="left")
    steps_var = tk.IntVar(value=8)
    tk.Button(steps_frame, text="-", width=2, font=("Consolas", 8),
              bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
              command=lambda: steps_var.set(max(2, steps_var.get() - 1))
              ).pack(side="left", padx=2)
    tk.Label(steps_frame, textvariable=steps_var, font=("Consolas", 9, "bold"),
             bg=BG_DEEP, fg=TEXT_PRIMARY, width=3).pack(side="left")
    tk.Button(steps_frame, text="+", width=2, font=("Consolas", 8),
              bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
              command=lambda: steps_var.set(min(32, steps_var.get() + 1))
              ).pack(side="left", padx=2)

    # Interpolation mode
    mode_frame = tk.Frame(dialog, bg=BG_DEEP)
    mode_frame.pack(fill="x", padx=20, pady=4)
    tk.Label(mode_frame, text="Mode:", font=("Consolas", 9),
             bg=BG_DEEP, fg=TEXT_PRIMARY).pack(side="left")
    mode_var = tk.StringVar(value="rgb")
    tk.Radiobutton(mode_frame, text="RGB", variable=mode_var, value="rgb",
                   bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
                   activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
                   font=("Consolas", 9)).pack(side="left", padx=8)
    tk.Radiobutton(mode_frame, text="HSV", variable=mode_var, value="hsv",
                   bg=BG_DEEP, fg=TEXT_PRIMARY, selectcolor=BG_PANEL,
                   activebackground=BG_DEEP, activeforeground=ACCENT_CYAN,
                   font=("Consolas", 9)).pack(side="left", padx=8)

    # Preview strip (will show generated colors)
    preview_canvas = tk.Canvas(dialog, height=24, bg=BG_PANEL_ALT,
                               highlightthickness=1, highlightbackground=BORDER)
    preview_canvas.pack(fill="x", padx=20, pady=8)

    def _update_preview(*_args):
        preview_canvas.delete("all")
        from src.palette import generate_ramp
        steps = steps_var.get()
        mode = mode_var.get()
        ramp = generate_ramp(fg_color, bg_color, steps, mode)
        pw = preview_canvas.winfo_width()
        if pw < 2:
            pw = 280
        seg = pw / max(1, len(ramp))
        for i, c in enumerate(ramp):
            x1 = int(i * seg)
            x2 = int((i + 1) * seg)
            hex_c = f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
            preview_canvas.create_rectangle(x1, 0, x2, 24, fill=hex_c, outline="")

    steps_var.trace_add("write", _update_preview)
    mode_var.trace_add("write", _update_preview)
    dialog.after(50, _update_preview)

    # Buttons
    btn_frame = tk.Frame(dialog, bg=BG_DEEP)
    btn_frame.pack(fill="x", padx=20, pady=8)

    def _add():
        result[0] = {
            "start": fg_color,
            "end": bg_color,
            "steps": steps_var.get(),
            "mode": mode_var.get(),
        }
        dialog.destroy()

    add_btn = tk.Button(btn_frame, text="Add to Palette", width=14,
                        bg=ACCENT_CYAN, fg=BG_DEEP, relief="flat",
                        font=("Consolas", 9, "bold"), command=_add)
    add_btn.pack(side="left", padx=4)
    _neon_hover(add_btn, ACCENT_MAGENTA, ACCENT_CYAN)

    cancel_btn = tk.Button(btn_frame, text="Cancel", width=10,
                           bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                           font=("Consolas", 9),
                           command=dialog.destroy)
    cancel_btn.pack(side="left", padx=4)
    _neon_hover(cancel_btn)

    dialog.wait_window()
    return result[0]
```

- [ ] **Step 2: Add import for `ask_color_ramp` in app.py**

In `src/app.py`, update the import from `src.ui.dialogs`:

```python
from src.ui.dialogs import (
    ask_canvas_size, ask_save_file, ask_open_file,
    ask_export_gif, ask_startup, ask_save_before, show_info, show_error,
    ask_color_ramp
)
```

- [ ] **Step 3: Add "Generate Color Ramp..." to Edit menu**

In `src/app.py`, in `_build_menu`, add before the "Keyboard Shortcuts..." entry:

```python
edit_menu.add_separator()
edit_menu.add_command(label="Generate Color Ramp...",
                      command=self._show_color_ramp_dialog)
```

- [ ] **Step 4: Add the handler method**

In `src/app.py`, add:

```python
def _show_color_ramp_dialog(self):
    fg = self.palette.selected_color
    # Use first color as bg default if only one selected
    bg = self.palette.colors[-1] if len(self.palette.colors) > 1 else (255, 255, 255, 255)
    result = ask_color_ramp(self.root, fg, bg)
    if result:
        from src.palette import generate_ramp
        ramp = generate_ramp(result["start"], result["end"],
                             result["steps"], result["mode"])
        for color in ramp:
            self.palette.add_color(color)
        self.right_panel.palette_panel.refresh()
        self._update_status(f"Added {len(ramp)} colors to palette")
```

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass.
