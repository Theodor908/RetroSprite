# PhotoImage Rendering Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace per-pixel `create_rectangle()` rendering with PIL Image → `ImageTk.PhotoImage` single-item rendering to eliminate freezing on large canvases (up to 256x256+).

**Architecture:** Hybrid approach — pixel layer and onion skin rendered via PIL compositing into a single `ImageTk.PhotoImage` canvas item. Overlays (cursor, selection, line/rect previews) remain as lightweight Tk canvas items (1-25 items max, negligible cost). Floating paste preview also converted to PhotoImage.

**Tech Stack:** Pillow (PIL) for image compositing, `ImageTk.PhotoImage` for Tk display, `ImageDraw` for grid lines.

---

### Task 1: Core render() rewrite — PIL-based pixel rendering

**Files:**
- Modify: `src/canvas.py:1-134`
- Test: `tests/test_canvas_rendering.py` (create)

**Step 1: Write the failing test**

Create `tests/test_canvas_rendering.py`:

```python
"""Tests for PIL-based canvas rendering pipeline."""
import pytest
from PIL import Image
from src.pixel_data import PixelGrid
from src.canvas import build_render_image


class TestBuildRenderImage:
    def test_empty_grid_returns_bg_color(self):
        """Empty grid should produce solid #2b2b2b background."""
        grid = PixelGrid(4, 4)
        img = build_render_image(grid, pixel_size=10, show_grid=False)
        assert img.size == (40, 40)
        # Sample center of first pixel cell — should be bg color
        assert img.getpixel((5, 5)) == (43, 43, 43)

    def test_opaque_pixel_renders_correct_color(self):
        """A fully opaque red pixel should render as pure red."""
        grid = PixelGrid(4, 4)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        img = build_render_image(grid, pixel_size=10, show_grid=False)
        # Center of pixel (0,0) cell
        assert img.getpixel((5, 5)) == (255, 0, 0)

    def test_semi_transparent_pixel_blends_with_bg(self):
        """A 50% alpha white pixel over #2b2b2b should blend."""
        grid = PixelGrid(4, 4)
        grid.set_pixel(0, 0, (255, 255, 255, 128))
        img = build_render_image(grid, pixel_size=10, show_grid=False)
        r, g, b = img.getpixel((5, 5))
        # Should be between bg (43) and white (255)
        assert 130 < r < 170
        assert r == g == b

    def test_pixel_size_1_produces_correct_dimensions(self):
        """At pixel_size=1, output should match grid dimensions exactly."""
        grid = PixelGrid(16, 8)
        img = build_render_image(grid, pixel_size=1, show_grid=False)
        assert img.size == (16, 8)

    def test_grid_lines_drawn_when_enabled(self):
        """Grid lines should appear when show_grid=True and ps >= 4."""
        grid = PixelGrid(4, 4)
        img_no_grid = build_render_image(grid, pixel_size=10, show_grid=False)
        img_with_grid = build_render_image(grid, pixel_size=10, show_grid=True)
        # Grid lines change pixels at cell boundaries
        # Pixel at x=10 (boundary) should differ
        assert img_no_grid.getpixel((10, 5)) != img_with_grid.getpixel((10, 5))

    def test_grid_lines_not_drawn_when_pixel_size_small(self):
        """Grid lines should not appear when pixel_size < 4."""
        grid = PixelGrid(4, 4)
        img_no_grid = build_render_image(grid, pixel_size=2, show_grid=False)
        img_with_grid = build_render_image(grid, pixel_size=2, show_grid=True)
        # At ps=2, grid should be suppressed — images should be identical
        assert list(img_no_grid.getdata()) == list(img_with_grid.getdata())
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_canvas_rendering.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_render_image'`

**Step 3: Implement `build_render_image` and rewrite `render()`**

In `src/canvas.py`, add imports at top:

```python
from PIL import Image, ImageDraw, ImageTk
```

Add module-level helper function (before the class):

```python
def build_render_image(grid: PixelGrid, pixel_size: int,
                       show_grid: bool,
                       onion_grid: PixelGrid | None = None) -> Image.Image:
    """Build a PIL RGB image of the canvas at the given zoom level.

    Composites: background → onion skin (optional) → current frame → grid lines.
    Returns an RGB image ready for ImageTk.PhotoImage conversion.
    """
    w, h = grid.width, grid.height
    bg = Image.new("RGBA", (w, h), (43, 43, 43, 255))

    # Onion skin layer (tinted, semi-transparent previous frame)
    if onion_grid is not None:
        onion_img = onion_grid.to_pil_image()
        # Tint: halve color channels and add 128, then set alpha to ~64
        onion_data = []
        for r, g, b, a in onion_img.getdata():
            if a > 0:
                tr = min(255, r // 2 + 128)
                tg = min(255, g // 2 + 128)
                tb = min(255, b // 2 + 128)
                onion_data.append((tr, tg, tb, 64))
            else:
                onion_data.append((0, 0, 0, 0))
        onion_layer = Image.new("RGBA", (w, h))
        onion_layer.putdata(onion_data)
        bg = Image.alpha_composite(bg, onion_layer)

    # Current frame layer
    frame_img = grid.to_pil_image()
    bg = Image.alpha_composite(bg, frame_img)

    # Convert to RGB (no more alpha needed) and scale up
    rgb = bg.convert("RGB")
    scaled = rgb.resize((w * pixel_size, h * pixel_size), Image.NEAREST)

    # Grid lines
    if show_grid and pixel_size >= 4:
        draw = ImageDraw.Draw(scaled)
        grid_color = (58, 58, 58)  # #3a3a3a
        sw, sh = scaled.size
        for x in range(0, sw + 1, pixel_size):
            draw.line([(x, 0), (x, sh - 1)], fill=grid_color)
        for y in range(0, sh + 1, pixel_size):
            draw.line([(0, y), (sw - 1, y)], fill=grid_color)

    return scaled
```

Rewrite `render()` method in `PixelCanvas` class:

```python
def render(self, onion_grid: PixelGrid | None = None) -> None:
    self.delete("pixel")
    img = build_render_image(self.grid, self.pixel_size, self.show_grid,
                             onion_grid)
    self._photo = ImageTk.PhotoImage(img)
    self.create_image(0, 0, image=self._photo, anchor="nw", tags="pixel")
    # Raise overlays above the image
    self.tag_raise("overlay")
    self.tag_raise("selection")
    self.tag_raise("floating")
```

Remove the old `_draw_grid` method (lines 136-144) — grid drawing is now inside `build_render_image`.

Remove the old `render_onion_skin` method (lines 236-251) — onion skin is now composited inside `build_render_image` via the `onion_grid` parameter.

Add `self._photo = None` in `__init__` (after `self.show_grid = True`) to initialize the PhotoImage reference.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_canvas_rendering.py -v`
Expected: All 6 tests PASS

**Step 5: Run all existing tests to verify no regressions**

Run: `python -m pytest tests/ -v`
Expected: All existing tests still PASS (canvas.py changes don't affect tool/data tests)

**Step 6: Commit**

```bash
git add src/canvas.py tests/test_canvas_rendering.py
git commit -m "feat: replace per-pixel create_rectangle with PIL PhotoImage rendering"
```

---

### Task 2: Update app.py to pass onion_grid through render()

**Files:**
- Modify: `src/app.py:832-841`

**Step 1: Update `_render_canvas` to pass onion grid to render()**

In `src/app.py`, change `_render_canvas` (lines 832-841) from:

```python
def _render_canvas(self):
    self.pixel_canvas.render()
    # Onion skin: show previous frame when enabled and not on first frame
    if self._onion_skin and self.timeline.current_index > 0:
        prev = self.timeline.get_frame(self.timeline.current_index - 1)
        self.pixel_canvas.render_onion_skin(prev)
    # Re-draw persistent selection if active
    if self._selection:
        x0, y0, x1, y1 = self._selection
        self.pixel_canvas.draw_selection(x0, y0, x1, y1)
```

To:

```python
def _render_canvas(self):
    onion = None
    if self._onion_skin and self.timeline.current_index > 0:
        onion = self.timeline.get_frame(self.timeline.current_index - 1)
    self.pixel_canvas.render(onion_grid=onion)
    # Re-draw persistent selection if active
    if self._selection:
        x0, y0, x1, y1 = self._selection
        self.pixel_canvas.draw_selection(x0, y0, x1, y1)
```

**Step 2: Update `_refresh_canvas` similarly**

Change `_refresh_canvas` (lines 822-830) from:

```python
def _refresh_canvas(self):
    self.pixel_canvas.set_grid(self.timeline.current_frame())
    # Re-apply onion skin and selection after grid swap
    if self._onion_skin and self.timeline.current_index > 0:
        prev = self.timeline.get_frame(self.timeline.current_index - 1)
        self.pixel_canvas.render_onion_skin(prev)
    if self._selection:
        x0, y0, x1, y1 = self._selection
        self.pixel_canvas.draw_selection(x0, y0, x1, y1)
```

To:

```python
def _refresh_canvas(self):
    self.pixel_canvas.set_grid(self.timeline.current_frame())
    # set_grid calls render() without onion — re-render with onion if needed
    onion = None
    if self._onion_skin and self.timeline.current_index > 0:
        onion = self.timeline.get_frame(self.timeline.current_index - 1)
    if onion:
        self.pixel_canvas.render(onion_grid=onion)
    if self._selection:
        x0, y0, x1, y1 = self._selection
        self.pixel_canvas.draw_selection(x0, y0, x1, y1)
```

**Step 3: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add src/app.py
git commit -m "feat: pass onion grid through render() for single-pass compositing"
```

---

### Task 3: Convert `draw_floating_pixels` to PhotoImage

**Files:**
- Modify: `src/canvas.py` — `draw_floating_pixels` method

**Step 1: Write the failing test**

Add to `tests/test_canvas_rendering.py`:

```python
class TestBuildFloatingImage:
    def test_floating_image_correct_size(self):
        from src.canvas import build_floating_image
        source = PixelGrid(4, 3)
        source.set_pixel(0, 0, (255, 0, 0, 255))
        img = build_floating_image(source, pixel_size=10)
        assert img.size == (40, 30)

    def test_floating_image_has_transparency(self):
        from src.canvas import build_floating_image
        source = PixelGrid(4, 3)
        source.set_pixel(0, 0, (255, 0, 0, 255))
        img = build_floating_image(source, pixel_size=10)
        # Transparent pixel cell should have alpha=0
        assert img.mode == "RGBA"
        assert img.getpixel((15, 15))[3] == 0

    def test_floating_image_opaque_pixel(self):
        from src.canvas import build_floating_image
        source = PixelGrid(4, 3)
        source.set_pixel(0, 0, (255, 0, 0, 255))
        img = build_floating_image(source, pixel_size=10)
        r, g, b, a = img.getpixel((5, 5))
        assert (r, g, b) == (255, 0, 0)
        assert a == 255
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_canvas_rendering.py::TestBuildFloatingImage -v`
Expected: FAIL with `ImportError: cannot import name 'build_floating_image'`

**Step 3: Implement `build_floating_image` and rewrite `draw_floating_pixels`**

Add helper function in `src/canvas.py` (after `build_render_image`):

```python
def build_floating_image(source: PixelGrid, pixel_size: int) -> Image.Image:
    """Build an RGBA image for the floating paste preview."""
    img = source.to_pil_image()
    scaled = img.resize((source.width * pixel_size, source.height * pixel_size),
                        Image.NEAREST)
    return scaled
```

Rewrite `draw_floating_pixels` method:

```python
def draw_floating_pixels(self, source: PixelGrid, gx: int, gy: int) -> None:
    """Draw a floating pixel grid overlay at grid position (gx, gy)."""
    self.delete("floating")
    ps = self.pixel_size
    img = build_floating_image(source, ps)
    self._floating_photo = ImageTk.PhotoImage(img)
    self.create_image(gx * ps, gy * ps, image=self._floating_photo,
                      anchor="nw", tags="floating")
    # Draw bounding box around the floating selection
    self.create_rectangle(
        gx * ps, gy * ps,
        (gx + source.width) * ps, (gy + source.height) * ps,
        outline="#00bfff", dash=(4, 4), width=2, fill="",
        tags="floating"
    )
```

Add `self._floating_photo = None` in `__init__`.

**Step 4: Run tests**

Run: `python -m pytest tests/test_canvas_rendering.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/canvas.py tests/test_canvas_rendering.py
git commit -m "feat: convert floating paste preview to PhotoImage rendering"
```

---

### Task 4: Convert AnimationPreview.render_frame to PhotoImage

**Files:**
- Modify: `src/ui/right_panel.py:272-283`

**Step 1: Write the failing test**

Add to `tests/test_canvas_rendering.py`:

```python
class TestBuildPreviewImage:
    def test_preview_correct_size(self):
        from src.canvas import build_render_image
        grid = PixelGrid(32, 32)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        # Preview uses pixel_size = preview_size // max(w, h)
        ps = max(1, 80 // max(grid.width, grid.height))
        img = build_render_image(grid, pixel_size=ps, show_grid=False)
        assert img.size == (32 * ps, 32 * ps)

    def test_preview_renders_pixel(self):
        from src.canvas import build_render_image
        grid = PixelGrid(8, 8)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        ps = max(1, 80 // 8)
        img = build_render_image(grid, pixel_size=ps, show_grid=False)
        r, g, b = img.getpixel((ps // 2, ps // 2))
        assert (r, g, b) == (255, 0, 0)
```

**Step 2: Run test to verify it passes (reuses existing build_render_image)**

Run: `python -m pytest tests/test_canvas_rendering.py::TestBuildPreviewImage -v`
Expected: PASS (function already exists from Task 1)

**Step 3: Rewrite `AnimationPreview.render_frame`**

In `src/ui/right_panel.py`, add import at top (line 5 already has `from PIL import Image, ImageTk`):

```python
from src.canvas import build_render_image
```

Replace `render_frame` (lines 272-283):

```python
def render_frame(self, grid, preview_size=80):
    self.preview_canvas.delete("all")
    ps = max(1, preview_size // max(grid.width, grid.height))
    img = build_render_image(grid, pixel_size=ps, show_grid=False)
    self._preview_photo = ImageTk.PhotoImage(img)
    self.preview_canvas.create_image(0, 0, image=self._preview_photo,
                                     anchor="nw")
```

Add `self._preview_photo = None` in `AnimationPreview.__init__` (after the `self._controls_frame = None` line).

**Step 4: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/ui/right_panel.py tests/test_canvas_rendering.py
git commit -m "feat: convert animation preview to PhotoImage rendering"
```

---

### Task 5: Cleanup — remove dead code and run final verification

**Files:**
- Modify: `src/canvas.py` — remove old `_draw_grid` and `render_onion_skin` methods if still present

**Step 1: Verify old methods are removed**

Ensure `src/canvas.py` no longer contains:
- `_draw_grid` method (grid drawing moved to `build_render_image`)
- `render_onion_skin` method (onion skin moved to `build_render_image` via `onion_grid` param)

If they still exist, delete them.

**Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS

**Step 3: Manual smoke test**

Run: `python main.py`

Test these scenarios:
1. Create a 128x128 canvas → use Fill tool on empty canvas → should be instant (not freeze)
2. Draw with Pen tool on filled canvas → should be smooth
3. Toggle onion skin on with multiple frames → should render correctly
4. Use paste (Ctrl+C / Ctrl+V) → floating preview should follow mouse smoothly
5. Play animation → preview panel should animate smoothly
6. Zoom in/out → grid lines should appear/disappear at zoom >= 4px
7. Use selection tool → marching-ants rectangle should work

**Step 4: Commit cleanup**

```bash
git add src/canvas.py
git commit -m "chore: remove dead rendering methods replaced by PIL pipeline"
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `src/canvas.py` | New `build_render_image()` and `build_floating_image()` functions. `render()` rewritten to use single PhotoImage. `draw_floating_pixels()` rewritten. `_draw_grid()` and `render_onion_skin()` removed. |
| `src/app.py` | `_render_canvas()` and `_refresh_canvas()` pass `onion_grid` to `render()` instead of calling `render_onion_skin()` separately. |
| `src/ui/right_panel.py` | `AnimationPreview.render_frame()` uses `build_render_image()` instead of per-pixel `create_rectangle()`. |
| `tests/test_canvas_rendering.py` | New test file with tests for `build_render_image` and `build_floating_image`. |

**No changes to:** `src/tools.py`, `src/pixel_data.py`, `src/animation.py`, `src/project.py`, `src/palette.py`, `src/compression.py`, `src/ui/toolbar.py`, `src/ui/dialogs.py`
