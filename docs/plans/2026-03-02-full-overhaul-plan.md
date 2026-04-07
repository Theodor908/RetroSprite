# RetroSprite Full Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform RetroSprite from a basic pixel art editor into a professional-grade tool with NumPy performance, layers, advanced drawing tools, pro animation, quality-of-life features, and a striking neon retro visual theme.

**Architecture:** Bottom-up rebuild — migrate the data backend to NumPy first (all downstream code benefits), add Layer model that wraps PixelGrid, upgrade the render pipeline, then add tools/features/UI on top of the new foundation. Each phase builds on the previous.

**Tech Stack:** Python 3.8+, NumPy, Pillow, Tkinter, imageio, pytest

---

## Phase 1: Foundation

### Task 1: Add NumPy dependency

**Files:**
- Modify: `requirements.txt`

**Step 1:** Add numpy to requirements.txt

Add `numpy>=1.24` to `requirements.txt` after the Pillow line.

**Step 2:** Install dependencies

Run: `pip install -r requirements.txt`
Expected: Successfully installed numpy

**Step 3:** Commit

```bash
git add requirements.txt
git commit -m "chore: add numpy dependency"
```

---

### Task 2: Migrate PixelGrid to NumPy backend

**Files:**
- Modify: `src/pixel_data.py`
- Test: `tests/test_pixel_data.py` (existing tests must still pass)

**Step 1:** Rewrite PixelGrid with NumPy internals

Replace the contents of `src/pixel_data.py` with:

```python
"""Core pixel data model for RetroSprite."""
from __future__ import annotations
import numpy as np
from PIL import Image


class PixelGrid:
    """A 2D grid of RGBA pixel values backed by a NumPy array."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self._pixels = np.zeros((height, width, 4), dtype=np.uint8)

    def get_pixel(self, x: int, y: int) -> tuple[int, int, int, int] | None:
        if 0 <= x < self.width and 0 <= y < self.height:
            return tuple(int(v) for v in self._pixels[y, x])
        return None

    def set_pixel(self, x: int, y: int, color: tuple[int, int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self._pixels[y, x] = color

    def clear(self) -> None:
        self._pixels[:] = 0

    def to_flat_list(self) -> list[tuple[int, int, int, int]]:
        flat = self._pixels.reshape(-1, 4)
        return [tuple(int(v) for v in row) for row in flat]

    def to_pil_image(self) -> Image.Image:
        return Image.fromarray(self._pixels, "RGBA")

    @classmethod
    def from_pil_image(cls, img: Image.Image) -> PixelGrid:
        img = img.convert("RGBA")
        w, h = img.size
        grid = cls(w, h)
        grid._pixels = np.array(img, dtype=np.uint8)
        return grid

    def copy(self) -> PixelGrid:
        new_grid = PixelGrid(self.width, self.height)
        new_grid._pixels = self._pixels.copy()
        return new_grid

    def extract_region(self, x: int, y: int, w: int, h: int) -> PixelGrid:
        """Extract a rectangular sub-region as a new PixelGrid."""
        region = PixelGrid(w, h)
        for ry in range(h):
            for rx in range(w):
                sx, sy = x + rx, y + ry
                if 0 <= sx < self.width and 0 <= sy < self.height:
                    region._pixels[ry, rx] = self._pixels[sy, sx]
        return region

    def paste_region(self, source: PixelGrid, x: int, y: int) -> None:
        """Paste another PixelGrid onto this grid at (x, y), skipping transparent pixels."""
        for sy in range(source.height):
            for sx in range(source.width):
                if source._pixels[sy, sx, 3] > 0:
                    tx, ty = x + sx, y + sy
                    if 0 <= tx < self.width and 0 <= ty < self.height:
                        self._pixels[ty, tx] = source._pixels[sy, sx]
```

**Step 2:** Run existing tests to verify backward compatibility

Run: `python -m pytest tests/test_pixel_data.py -v`
Expected: All 14 tests PASS. The public API is identical.

**Step 3:** Run full test suite

Run: `python -m pytest tests/ -v`
Expected: All tests PASS. Every module that uses PixelGrid works unchanged because get_pixel/set_pixel/to_flat_list return the same types.

**Step 4:** Commit

```bash
git add src/pixel_data.py
git commit -m "perf: migrate PixelGrid to NumPy backend"
```

---

### Task 3: Optimize render pipeline

**Files:**
- Modify: `src/canvas.py`

**Step 1:** Optimize `build_render_image` — vectorize onion skin and cache grid

Replace onion skin Python loop (lines 20-31) with NumPy vectorized operation, and add grid caching:

In `build_render_image`, replace the onion skin block:
```python
    if onion_grid is not None and onion_grid.width == w and onion_grid.height == h:
        onion_arr = onion_grid._pixels.copy()
        mask = onion_arr[:, :, 3] > 0
        onion_arr[mask, 0] = np.minimum(255, onion_arr[mask, 0] // 2 + 128)
        onion_arr[mask, 1] = np.minimum(255, onion_arr[mask, 1] // 2 + 128)
        onion_arr[mask, 2] = np.minimum(255, onion_arr[mask, 2] // 2 + 128)
        onion_arr[mask, 3] = 64
        onion_layer = Image.fromarray(onion_arr, "RGBA")
        bg = Image.alpha_composite(bg, onion_layer)
```

Add `import numpy as np` at the top of `canvas.py`.

**Step 2:** Optimize `render()` — reuse canvas image item

In `PixelCanvas.__init__`, add: `self._image_id = None`

Replace `render()`:
```python
    def render(self, onion_grid: PixelGrid | None = None) -> None:
        img = build_render_image(self.grid, self.pixel_size, self.show_grid,
                                 onion_grid)
        self._photo = ImageTk.PhotoImage(img)
        if self._image_id is None:
            self._image_id = self.create_image(0, 0, image=self._photo,
                                                anchor="nw", tags="pixel")
        else:
            self.itemconfig(self._image_id, image=self._photo)
        self.tag_raise("overlay")
        self.tag_raise("selection")
        self.tag_raise("floating")
```

**Step 3:** Run canvas rendering tests

Run: `python -m pytest tests/test_canvas_rendering.py -v`
Expected: All PASS

**Step 4:** Commit

```bash
git add src/canvas.py
git commit -m "perf: vectorize onion skin, reuse canvas image item"
```

---

### Task 4: Add Layer model

**Files:**
- Create: `src/layer.py`
- Test: `tests/test_layer.py` (new)

**Step 1:** Write failing tests for Layer

Create `tests/test_layer.py`:

```python
"""Tests for layer model."""
import pytest
import numpy as np
from src.layer import Layer, flatten_layers
from src.pixel_data import PixelGrid


RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


class TestLayer:
    def test_create_layer(self):
        layer = Layer("Background", 8, 8)
        assert layer.name == "Background"
        assert layer.visible is True
        assert layer.opacity == 1.0
        assert layer.blend_mode == "normal"
        assert layer.locked is False
        assert layer.pixels.width == 8

    def test_layer_from_grid(self):
        grid = PixelGrid(4, 4)
        grid.set_pixel(0, 0, RED)
        layer = Layer.from_grid("Test", grid)
        assert layer.pixels.get_pixel(0, 0) == RED

    def test_layer_copy(self):
        layer = Layer("Original", 4, 4)
        layer.pixels.set_pixel(0, 0, RED)
        copy = layer.copy()
        copy.pixels.set_pixel(0, 0, GREEN)
        assert layer.pixels.get_pixel(0, 0) == RED
        assert copy.name == "Original Copy"


class TestFlattenLayers:
    def test_single_layer(self):
        layer = Layer("Base", 4, 4)
        layer.pixels.set_pixel(0, 0, RED)
        result = flatten_layers([layer], 4, 4)
        assert result.get_pixel(0, 0) == RED

    def test_two_layers_opaque(self):
        bottom = Layer("Bottom", 4, 4)
        bottom.pixels.set_pixel(0, 0, RED)
        top = Layer("Top", 4, 4)
        top.pixels.set_pixel(0, 0, GREEN)
        result = flatten_layers([bottom, top], 4, 4)
        assert result.get_pixel(0, 0) == GREEN

    def test_hidden_layer_ignored(self):
        bottom = Layer("Bottom", 4, 4)
        bottom.pixels.set_pixel(0, 0, RED)
        top = Layer("Top", 4, 4)
        top.pixels.set_pixel(0, 0, GREEN)
        top.visible = False
        result = flatten_layers([bottom, top], 4, 4)
        assert result.get_pixel(0, 0) == RED

    def test_layer_opacity(self):
        bottom = Layer("Bottom", 4, 4)
        bottom.pixels.set_pixel(0, 0, RED)
        top = Layer("Top", 4, 4)
        top.pixels.set_pixel(0, 0, GREEN)
        top.opacity = 0.5
        result = flatten_layers([bottom, top], 4, 4)
        pixel = result.get_pixel(0, 0)
        # Green at 50% over red: roughly (127, 128, 0, 255)
        assert pixel[0] < 200  # Red reduced
        assert pixel[1] > 50   # Green present
        assert pixel[3] == 255  # Fully opaque

    def test_empty_layers(self):
        result = flatten_layers([], 4, 4)
        assert result.get_pixel(0, 0) == TRANSPARENT
```

**Step 2:** Run tests to verify they fail

Run: `python -m pytest tests/test_layer.py -v`
Expected: FAIL — `src.layer` module not found

**Step 3:** Implement Layer model

Create `src/layer.py`:

```python
"""Layer model for RetroSprite."""
from __future__ import annotations
import numpy as np
from PIL import Image
from src.pixel_data import PixelGrid


class Layer:
    """A single compositing layer containing pixel data and display properties."""

    def __init__(self, name: str, width: int, height: int):
        self.name = name
        self.pixels = PixelGrid(width, height)
        self.visible: bool = True
        self.opacity: float = 1.0
        self.blend_mode: str = "normal"
        self.locked: bool = False

    @classmethod
    def from_grid(cls, name: str, grid: PixelGrid) -> Layer:
        layer = cls(name, grid.width, grid.height)
        layer.pixels._pixels = grid._pixels.copy()
        return layer

    def copy(self) -> Layer:
        new_layer = Layer(f"{self.name} Copy", self.pixels.width, self.pixels.height)
        new_layer.pixels._pixels = self.pixels._pixels.copy()
        new_layer.visible = self.visible
        new_layer.opacity = self.opacity
        new_layer.blend_mode = self.blend_mode
        new_layer.locked = self.locked
        return new_layer


def flatten_layers(layers: list[Layer], width: int, height: int) -> PixelGrid:
    """Composite all visible layers into a single PixelGrid.

    Layers are composited bottom-to-top (index 0 = bottom).
    """
    base = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    for layer in layers:
        if not layer.visible:
            continue
        layer_img = layer.pixels.to_pil_image()
        if layer.opacity < 1.0:
            # Scale alpha channel by opacity
            arr = np.array(layer_img, dtype=np.uint8)
            arr[:, :, 3] = (arr[:, :, 3] * layer.opacity).astype(np.uint8)
            layer_img = Image.fromarray(arr, "RGBA")
        base = Image.alpha_composite(base, layer_img)

    return PixelGrid.from_pil_image(base)
```

**Step 4:** Run tests

Run: `python -m pytest tests/test_layer.py -v`
Expected: All PASS

**Step 5:** Commit

```bash
git add src/layer.py tests/test_layer.py
git commit -m "feat: add Layer model with compositing"
```

---

### Task 5: Integrate layers into AnimationTimeline

**Files:**
- Modify: `src/animation.py`
- Modify: `tests/test_animation.py`

**Step 1:** Add layer-aware frame model to AnimationTimeline

The `AnimationTimeline` needs to track layers per frame. For backward compatibility, the `current_frame()` method returns the flattened composite, while `current_layer()` returns the active layer for drawing.

Rewrite `src/animation.py`:

```python
"""Animation timeline and frame management."""
from __future__ import annotations
from src.pixel_data import PixelGrid
from src.layer import Layer, flatten_layers


class Frame:
    """A single animation frame containing one or more layers."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.layers: list[Layer] = [Layer("Layer 1", width, height)]
        self.active_layer_index: int = 0

    @property
    def active_layer(self) -> Layer:
        return self.layers[self.active_layer_index]

    def flatten(self) -> PixelGrid:
        return flatten_layers(self.layers, self.width, self.height)

    def add_layer(self, name: str | None = None) -> Layer:
        if name is None:
            name = f"Layer {len(self.layers) + 1}"
        layer = Layer(name, self.width, self.height)
        self.layers.append(layer)
        self.active_layer_index = len(self.layers) - 1
        return layer

    def remove_layer(self, index: int) -> None:
        if len(self.layers) > 1 and 0 <= index < len(self.layers):
            self.layers.pop(index)
            if self.active_layer_index >= len(self.layers):
                self.active_layer_index = len(self.layers) - 1

    def duplicate_layer(self, index: int) -> Layer:
        if 0 <= index < len(self.layers):
            copy = self.layers[index].copy()
            self.layers.insert(index + 1, copy)
            self.active_layer_index = index + 1
            return copy
        return self.layers[self.active_layer_index]

    def merge_down(self, index: int) -> None:
        """Merge layer at index into the layer below it."""
        if index > 0 and index < len(self.layers):
            above = self.layers[index]
            below = self.layers[index - 1]
            merged = flatten_layers([below, above], self.width, self.height)
            below.pixels._pixels = merged._pixels.copy()
            self.layers.pop(index)
            self.active_layer_index = index - 1

    def move_layer(self, from_idx: int, to_idx: int) -> None:
        if (0 <= from_idx < len(self.layers) and
                0 <= to_idx < len(self.layers)):
            layer = self.layers.pop(from_idx)
            self.layers.insert(to_idx, layer)

    def copy(self) -> Frame:
        new_frame = Frame(self.width, self.height)
        new_frame.layers = [layer.copy() for layer in self.layers]
        new_frame.active_layer_index = self.active_layer_index
        return new_frame


class AnimationTimeline:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self._frames: list[Frame] = [Frame(width, height)]
        self._current_index: int = 0
        self.fps: int = 10
        self.tags: list[dict] = []  # {"name": str, "color": str, "start": int, "end": int}

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    @property
    def current_index(self) -> int:
        return self._current_index

    def current_frame_obj(self) -> Frame:
        """Return the current Frame object (with layers)."""
        return self._frames[self._current_index]

    def current_frame(self) -> PixelGrid:
        """Return the flattened composite of current frame (backward compat)."""
        return self._frames[self._current_index].flatten()

    def current_layer(self) -> PixelGrid:
        """Return the active layer's pixel grid for drawing."""
        return self._frames[self._current_index].active_layer.pixels

    def get_frame(self, index: int) -> PixelGrid:
        """Return flattened composite of frame at index."""
        return self._frames[index].flatten()

    def get_frame_obj(self, index: int) -> Frame:
        return self._frames[index]

    def set_current(self, index: int) -> None:
        if 0 <= index < len(self._frames):
            self._current_index = index

    def add_frame(self) -> None:
        self._frames.append(Frame(self.width, self.height))

    def duplicate_frame(self, index: int) -> None:
        if 0 <= index < len(self._frames):
            copy = self._frames[index].copy()
            self._frames.insert(index + 1, copy)

    def remove_frame(self, index: int) -> None:
        if len(self._frames) > 1 and 0 <= index < len(self._frames):
            self._frames.pop(index)
            if self._current_index >= len(self._frames):
                self._current_index = len(self._frames) - 1

    def move_frame(self, from_idx: int, to_idx: int) -> None:
        if (0 <= from_idx < len(self._frames) and
                0 <= to_idx < len(self._frames)):
            frame = self._frames.pop(from_idx)
            self._frames.insert(to_idx, frame)

    def export_gif(self, filepath: str, fps: int = 10, scale: int = 1,
                   duration_ms: int | None = None) -> None:
        from PIL import Image
        frames: list[Image.Image] = []
        for frame_obj in self._frames:
            grid = frame_obj.flatten()
            img = grid.to_pil_image()
            if scale > 1:
                new_size = (img.width * scale, img.height * scale)
                img = img.resize(new_size, Image.NEAREST)
            alpha = img.split()[3]
            p_img = img.convert("RGB").convert("P", palette=Image.ADAPTIVE,
                                                colors=255)
            lut = [255] * 129 + [0] * 127
            transparency_mask = alpha.point(lut, "L")
            p_img.paste(255, transparency_mask)
            frames.append(p_img)

        frame_duration = duration_ms if duration_ms is not None else 1000 // fps
        frames[0].save(
            filepath, save_all=True, append_images=frames[1:],
            duration=frame_duration, loop=0, transparency=255, disposal=2
        )
```

**Step 2:** Run existing animation tests

Run: `python -m pytest tests/test_animation.py -v`
Expected: PASS (the public API — `current_frame()`, `get_frame()`, `add_frame()`, etc. — returns the same types)

**Step 3:** Run full suite

Run: `python -m pytest tests/ -v`
Expected: All PASS

**Step 4:** Commit

```bash
git add src/animation.py
git commit -m "feat: integrate layers into animation frames"
```

---

### Task 6: Update app.py to draw on active layer

**Files:**
- Modify: `src/app.py`

**Step 1:** Update all tool operations to draw on the active layer instead of the flattened frame

Key changes in `app.py`:
- Replace `self.timeline.current_frame()` with `self.timeline.current_layer()` in all drawing tool dispatch (`_on_canvas_click`, `_on_canvas_drag`, `_on_canvas_release`)
- Keep `self.timeline.current_frame()` (flattened) for rendering, display, and export
- Update `_push_undo` to snapshot the active layer only
- The `_refresh_canvas` already calls `self.timeline.current_frame()` which now returns the flattened composite

Specific edits:

In `_on_canvas_click`, `_on_canvas_drag`, `_on_canvas_release`: replace
```python
grid = self.timeline.current_frame()
```
with
```python
grid = self.timeline.current_layer()
```
for lines that use tools (Pen, Eraser, Blur, Fill, Line, Rect, Pick).

For Pick tool, use `self.timeline.current_frame()` (flattened) so it picks the visible composite color.

Update `_push_undo`:
```python
def _push_undo(self):
    snapshot = self.timeline.current_layer().copy()
    self._undo_stack.append((self.timeline.current_index,
                             self.timeline.current_frame_obj().active_layer_index,
                             snapshot))
```

Update `_undo` and `_redo` to restore the correct layer:
```python
def _undo(self):
    if not self._undo_stack:
        return
    frame_obj = self.timeline.current_frame_obj()
    layer_idx = frame_obj.active_layer_index
    current_layer = frame_obj.active_layer.pixels
    self._redo_stack.append((self.timeline.current_index, layer_idx,
                             current_layer.copy()))
    frame_idx, layer_idx, prev = self._undo_stack.pop()
    target_frame = self.timeline.get_frame_obj(frame_idx)
    target_frame.layers[layer_idx].pixels = prev
    self._refresh_canvas()
    self._update_status("Undo")
```

Similarly for `_redo`.

Update `_fill_selection`, `_delete_selection` to use `current_layer()`.

Update `_clear_canvas` to clear only the active layer.

**Step 2:** Run full test suite

Run: `python -m pytest tests/ -v`
Expected: All PASS

**Step 3:** Manually test the app

Run: `python main.py`
Verify: Drawing, erasing, filling all work correctly. The app should behave identically to before (single layer per frame by default).

**Step 4:** Commit

```bash
git add src/app.py
git commit -m "feat: wire tools to draw on active layer"
```

---

### Task 7: Update project save/load for layers

**Files:**
- Modify: `src/project.py`
- Test: `tests/test_project.py`

**Step 1:** Update save_project to serialize layers

```python
def save_project(filepath: str, timeline, palette) -> None:
    frames_data = []
    for i in range(timeline.frame_count):
        frame_obj = timeline.get_frame_obj(i)
        layers_data = []
        for layer in frame_obj.layers:
            pixels = layer.pixels.to_flat_list()
            layers_data.append({
                "name": layer.name,
                "visible": layer.visible,
                "opacity": layer.opacity,
                "blend_mode": layer.blend_mode,
                "locked": layer.locked,
                "pixels": [list(p) for p in pixels],
            })
        frames_data.append({
            "layers": layers_data,
            "active_layer": frame_obj.active_layer_index,
        })

    project = {
        "version": 2,
        "width": timeline.width,
        "height": timeline.height,
        "fps": timeline.fps,
        "current_frame": timeline.current_index,
        "palette_name": palette.name,
        "palette_colors": [list(c) for c in palette.colors],
        "selected_color_index": palette.selected_index,
        "frames": frames_data,
        "tags": timeline.tags,
    }

    with open(filepath, "w") as f:
        json.dump(project, f)
```

Update load_project to handle both v1 (flat pixels) and v2 (layers) formats.

**Step 2:** Run project tests

Run: `python -m pytest tests/test_project.py -v`
Expected: All PASS (v1 files still load correctly)

**Step 3:** Commit

```bash
git add src/project.py
git commit -m "feat: save/load layers in project format v2"
```

---

### Task 8: Add Layer Panel to right sidebar

**Files:**
- Modify: `src/ui/right_panel.py`
- Modify: `src/app.py`

**Step 1:** Create LayerPanel widget in right_panel.py

Add a new `LayerPanel` class after `FramePanel` that shows:
- Layer list (Listbox) with visibility indicators
- Add / Delete / Duplicate / Merge Down buttons
- Opacity slider (Scale widget)
- Active layer highlighted

**Step 2:** Wire LayerPanel into RightPanel and app.py

Add callbacks: `on_layer_select`, `on_add_layer`, `on_delete_layer`, `on_duplicate_layer`, `on_merge_down`, `on_opacity_change`, `on_visibility_toggle`.

**Step 3:** Manual test

Run: `python main.py`
Verify: Layer panel visible, can add/remove layers, draw on different layers, toggle visibility.

**Step 4:** Commit

```bash
git add src/ui/right_panel.py src/app.py
git commit -m "feat: add layer panel UI"
```

---

## Phase 2: New Drawing Tools

### Task 9: Add Ellipse tool

**Files:**
- Modify: `src/tools.py`
- Test: `tests/test_tools.py`
- Modify: `src/ui/toolbar.py`
- Modify: `src/app.py`

**Step 1:** Write failing test

Add to `tests/test_tools.py`:
```python
class TestEllipseTool:
    def test_draw_circle(self):
        grid = PixelGrid(16, 16)
        from src.tools import EllipseTool
        tool = EllipseTool()
        tool.apply(grid, 4, 4, 12, 12, RED, filled=False)
        # Check known circle points exist
        assert grid.get_pixel(8, 4) == RED   # top
        assert grid.get_pixel(8, 12) == RED  # bottom
        assert grid.get_pixel(4, 8) == RED   # left
        assert grid.get_pixel(12, 8) == RED  # right
        # Center should be empty (unfilled)
        assert grid.get_pixel(8, 8) == TRANSPARENT

    def test_draw_filled_ellipse(self):
        grid = PixelGrid(16, 16)
        from src.tools import EllipseTool
        tool = EllipseTool()
        tool.apply(grid, 4, 4, 12, 12, RED, filled=True)
        assert grid.get_pixel(8, 8) == RED
```

**Step 2:** Run test to verify it fails

Run: `python -m pytest tests/test_tools.py::TestEllipseTool -v`
Expected: FAIL — EllipseTool not found

**Step 3:** Implement EllipseTool using midpoint ellipse algorithm

Add to `src/tools.py`:
```python
class EllipseTool:
    def apply(self, grid: PixelGrid, x0: int, y0: int, x1: int, y1: int,
              color: tuple, filled: bool = False) -> None:
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        rx = abs(x1 - x0) // 2
        ry = abs(y1 - y0) // 2
        if rx == 0 or ry == 0:
            return
        self._draw_ellipse(grid, cx, cy, rx, ry, color, filled)

    def _draw_ellipse(self, grid, cx, cy, rx, ry, color, filled):
        x = 0
        y = ry
        rx2 = rx * rx
        ry2 = ry * ry
        px = 0
        py = 2 * rx2 * y

        if filled:
            self._fill_line(grid, cx - rx, cx + rx, cy, color)
        else:
            self._plot4(grid, cx, cy, x, y, color)

        # Region 1
        p1 = ry2 - rx2 * ry + 0.25 * rx2
        while px < py:
            x += 1
            px += 2 * ry2
            if p1 < 0:
                p1 += ry2 + px
            else:
                y -= 1
                py -= 2 * rx2
                p1 += ry2 + px - py
            if filled:
                self._fill_line(grid, cx - x, cx + x, cy + y, color)
                self._fill_line(grid, cx - x, cx + x, cy - y, color)
            else:
                self._plot4(grid, cx, cy, x, y, color)

        # Region 2
        p2 = ry2 * (x + 0.5) ** 2 + rx2 * (y - 1) ** 2 - rx2 * ry2
        while y > 0:
            y -= 1
            py -= 2 * rx2
            if p2 > 0:
                p2 += rx2 - py
            else:
                x += 1
                px += 2 * ry2
                p2 += rx2 - py + px
            if filled:
                self._fill_line(grid, cx - x, cx + x, cy + y, color)
                self._fill_line(grid, cx - x, cx + x, cy - y, color)
            else:
                self._plot4(grid, cx, cy, x, y, color)

    def _plot4(self, grid, cx, cy, x, y, color):
        grid.set_pixel(cx + x, cy + y, color)
        grid.set_pixel(cx - x, cy + y, color)
        grid.set_pixel(cx + x, cy - y, color)
        grid.set_pixel(cx - x, cy - y, color)

    def _fill_line(self, grid, x0, x1, y, color):
        for x in range(x0, x1 + 1):
            grid.set_pixel(x, y, color)
```

**Step 4:** Run tests

Run: `python -m pytest tests/test_tools.py -v`
Expected: All PASS

**Step 5:** Wire into toolbar and app.py

Add `("Ellipse", "O")` to `TOOLS` in `toolbar.py`.
Add `"Ellipse": EllipseTool()` to `_tools` in `app.py`.
Handle Ellipse in click/drag/release like Rect tool.

**Step 6:** Commit

```bash
git add src/tools.py src/ui/toolbar.py src/app.py tests/test_tools.py
git commit -m "feat: add ellipse tool with midpoint algorithm"
```

---

### Task 10: Add Symmetry/Mirror drawing mode

**Files:**
- Modify: `src/app.py`
- Modify: `src/ui/toolbar.py`

**Step 1:** Add symmetry state to app.py

```python
self._symmetry_mode = "off"  # off, horizontal, vertical, both
```

**Step 2:** Create `_apply_with_symmetry` wrapper

Every draw call goes through this — it mirrors the operation:
```python
def _apply_with_symmetry(self, tool_fn, x, y, *args, **kwargs):
    tool_fn(x, y, *args, **kwargs)
    cx = self.timeline.width // 2
    cy = self.timeline.height // 2
    if self._symmetry_mode in ("horizontal", "both"):
        tool_fn(2 * cx - x - 1, y, *args, **kwargs)
    if self._symmetry_mode in ("vertical", "both"):
        tool_fn(x, 2 * cy - y - 1, *args, **kwargs)
    if self._symmetry_mode == "both":
        tool_fn(2 * cx - x - 1, 2 * cy - y - 1, *args, **kwargs)
```

**Step 3:** Add symmetry toggle to toolbar

Add cycle button: Off → H → V → Both → Off. Shortcut: `M`.

**Step 4:** Draw symmetry center lines on canvas when active

**Step 5:** Commit

```bash
git add src/app.py src/ui/toolbar.py
git commit -m "feat: add symmetry/mirror drawing mode"
```

---

### Task 11: Add Magic Wand selection tool

**Files:**
- Modify: `src/tools.py`
- Test: `tests/test_tools.py`
- Modify: `src/app.py`

**Step 1:** Write failing test

```python
class TestMagicWandTool:
    def test_select_same_color_area(self):
        grid = PixelGrid(8, 8)
        for x in range(4):
            for y in range(4):
                grid.set_pixel(x, y, RED)
        from src.tools import MagicWandTool
        tool = MagicWandTool()
        selected = tool.apply(grid, 0, 0, tolerance=0)
        assert (0, 0) in selected
        assert (3, 3) in selected
        assert (4, 0) not in selected

    def test_tolerance_selects_similar(self):
        grid = PixelGrid(4, 4)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        grid.set_pixel(1, 0, (250, 5, 0, 255))
        from src.tools import MagicWandTool
        tool = MagicWandTool()
        selected = tool.apply(grid, 0, 0, tolerance=10)
        assert (1, 0) in selected
```

**Step 2:** Implement MagicWandTool

BFS flood fill that returns a set of coordinates instead of painting. Color distance check with tolerance.

**Step 3:** Wire into app.py — highlight selected pixels on canvas

**Step 4:** Commit

```bash
git add src/tools.py src/app.py tests/test_tools.py
git commit -m "feat: add magic wand selection tool"
```

---

### Task 12: Add Pixel-Perfect freehand mode

**Files:**
- Modify: `src/app.py`

**Step 1:** Add pixel-perfect state tracking

Track last 3 drawn points during pen drag. If they form an L-shape, undo the middle pixel before drawing the new one.

```python
self._pixel_perfect = False
self._pp_last_points = []  # list of (x, y) for pixel-perfect tracking
```

**Step 2:** Implement L-shape detection in `_on_canvas_drag` for Pen tool

If 3 consecutive points form a right angle (e.g., (1,1) → (2,1) → (2,2)), erase the middle point (2,1) and draw at (2,2) directly from (1,1).

**Step 3:** Add toggle to toolbar

**Step 4:** Commit

```bash
git add src/app.py src/ui/toolbar.py
git commit -m "feat: add pixel-perfect freehand mode"
```

---

### Task 13: Add Dithering brushes

**Files:**
- Modify: `src/tools.py`
- Modify: `src/app.py`
- Modify: `src/ui/toolbar.py`

**Step 1:** Define dithering patterns

```python
DITHER_PATTERNS = {
    "none": None,
    "checker": [[1, 0], [0, 1]],
    "25%": [[1, 0, 0, 0], [0, 0, 0, 0], [0, 0, 1, 0], [0, 0, 0, 0]],
    "50%": [[1, 0], [0, 1]],
    "75%": [[1, 1], [1, 0]],
}
```

**Step 2:** Modify PenTool to accept a dither pattern

Before drawing each pixel, check `pattern[y % h][x % w]`. Only draw if the pattern value is 1.

**Step 3:** Add pattern selector to toolbar

Cycle button or dropdown. Shortcut: `D`.

**Step 4:** Commit

```bash
git add src/tools.py src/app.py src/ui/toolbar.py
git commit -m "feat: add dithering brush patterns"
```

---

### Task 14: Add Shading Ink tool

**Files:**
- Modify: `src/tools.py`
- Test: `tests/test_tools.py`
- Modify: `src/app.py`

**Step 1:** Write failing test

```python
class TestShadingInkTool:
    def test_lighten(self):
        from src.tools import ShadingInkTool
        palette = [(0, 0, 0, 255), (128, 0, 0, 255), (255, 0, 0, 255)]
        grid = PixelGrid(4, 4)
        grid.set_pixel(0, 0, (128, 0, 0, 255))
        tool = ShadingInkTool()
        tool.apply(grid, 0, 0, palette, mode="lighten")
        assert grid.get_pixel(0, 0) == (255, 0, 0, 255)
```

**Step 2:** Implement ShadingInkTool

Find closest palette color, shift one index lighter/darker.

**Step 3:** Wire shortcuts: `[` darken, `]` lighten

**Step 4:** Commit

```bash
git add src/tools.py src/app.py tests/test_tools.py
git commit -m "feat: add shading ink tool"
```

---

### Task 15: Add Gradient Fill

**Files:**
- Modify: `src/tools.py`
- Modify: `src/app.py`

**Step 1:** Implement gradient fill with Bayer dithering

Uses ordered dithering (4x4 Bayer matrix) to create pixel-art-appropriate gradients between two colors across a selection or canvas.

**Step 2:** Add to Image menu

**Step 3:** Commit

```bash
git add src/tools.py src/app.py
git commit -m "feat: add gradient fill with Bayer dithering"
```

---

## Phase 3: Animation Enhancements

### Task 16: Add frame tags

**Files:**
- Modify: `src/animation.py` (tags already stubbed)
- Modify: `src/ui/right_panel.py`
- Modify: `src/app.py`

**Step 1:** Add tag management methods to AnimationTimeline

```python
def add_tag(self, name, color, start, end): ...
def remove_tag(self, index): ...
def get_tags_for_frame(self, frame_index): ...
```

**Step 2:** Add tag display in frame panel (colored indicators)

**Step 3:** Commit

```bash
git add src/animation.py src/ui/right_panel.py src/app.py
git commit -m "feat: add frame tags for animation organization"
```

---

### Task 17: Add playback modes

**Files:**
- Modify: `src/app.py`

**Step 1:** Add playback mode state

```python
self._playback_mode = "forward"  # forward, reverse, pingpong
self._pingpong_direction = 1
```

**Step 2:** Update `_animate_step` for reverse and ping-pong

**Step 3:** Add mode selector in animation controls

**Step 4:** Commit

```bash
git add src/app.py src/ui/right_panel.py
git commit -m "feat: add reverse and ping-pong playback modes"
```

---

### Task 18: Thread GIF export

**Files:**
- Modify: `src/app.py`

**Step 1:** Move export to background thread

```python
def _export_gif(self):
    path = ask_export_gif(self.root)
    if not path:
        return
    self._update_status("Exporting GIF...")

    def worker():
        try:
            duration = self.right_panel.animation_preview.frame_duration_ms
            self.timeline.export_gif(path, fps=self.timeline.fps, scale=4,
                                     duration_ms=duration)
            self.root.after(0, lambda: show_info(self.root, "Export",
                                                  f"GIF saved to {path}"))
        except Exception as e:
            self.root.after(0, lambda: show_error(self.root, "Export Error",
                                                   str(e)))
        finally:
            self.root.after(0, lambda: self._update_status(""))

    import threading
    threading.Thread(target=worker, daemon=True).start()
```

**Step 2:** Commit

```bash
git add src/app.py
git commit -m "perf: thread GIF export to prevent UI freeze"
```

---

## Phase 4: Quality of Life

### Task 19: Add Sprite Sheet export

**Files:**
- Create: `src/export.py`
- Test: `tests/test_export.py`
- Modify: `src/app.py`

**Step 1:** Write failing test

```python
def test_export_sprite_sheet():
    from src.export import build_sprite_sheet
    from src.animation import AnimationTimeline
    timeline = AnimationTimeline(8, 8)
    timeline.add_frame()
    sheet, metadata = build_sprite_sheet(timeline, scale=1, columns=2)
    assert sheet.size == (16, 8)
    assert len(metadata["frames"]) == 2
```

**Step 2:** Implement `build_sprite_sheet`

Returns PIL Image + JSON metadata dict.

**Step 3:** Add export dialog to File menu

**Step 4:** Commit

```bash
git add src/export.py tests/test_export.py src/app.py
git commit -m "feat: add sprite sheet export with JSON metadata"
```

---

### Task 20: Add auto-save

**Files:**
- Modify: `src/app.py`

**Step 1:** Add auto-save timer

```python
self._dirty = False
self._auto_save_interval = 60000  # 60 seconds
self._schedule_auto_save()

def _schedule_auto_save(self):
    if self._dirty and self._project_path:
        try:
            save_project(self._project_path, self.timeline, self.palette)
            self._update_status("Auto-saved")
            self.root.after(2000, lambda: self._update_status(""))
            self._dirty = False
        except Exception:
            pass
    self.root.after(self._auto_save_interval, self._schedule_auto_save)
```

**Step 2:** Set `self._dirty = True` in `_push_undo` and clear on save

**Step 3:** Commit

```bash
git add src/app.py
git commit -m "feat: add auto-save every 60 seconds"
```

---

### Task 21: Add customizable keyboard shortcuts

**Files:**
- Create: `src/keybindings.py`
- Modify: `src/app.py`

**Step 1:** Create keybindings manager

Loads from `~/.retrosprite/keybindings.json`, falls back to defaults.

**Step 2:** Replace hardcoded key bindings in `_bind_keys` with configurable mappings

**Step 3:** Commit

```bash
git add src/keybindings.py src/app.py
git commit -m "feat: add customizable keyboard shortcuts"
```

---

### Task 22: Add reference image overlay

**Files:**
- Modify: `src/app.py`
- Modify: `src/canvas.py`

**Step 1:** Add reference image state to app

```python
self._reference_image = None  # PIL Image or None
self._reference_opacity = 0.3
self._reference_visible = False
```

**Step 2:** Render reference image in `build_render_image` between background and pixel data

**Step 3:** Add File menu → "Load Reference Image..." and Ctrl+R toggle

**Step 4:** Commit

```bash
git add src/app.py src/canvas.py
git commit -m "feat: add reference image overlay"
```

---

## Phase 5: Neon Retro Visual Theme

### Task 23: Create theme system

**Files:**
- Create: `src/ui/theme.py`

**Step 1:** Define the neon retro color constants and widget styling functions

```python
"""Neon Retro theme for RetroSprite."""

# Color palette
BG_DEEP = "#0d0d12"
BG_PANEL = "#14141f"
BG_PANEL_ALT = "#1a1a2e"
BORDER = "#1e1e3a"
TEXT_PRIMARY = "#e0e0e8"
TEXT_SECONDARY = "#7a7a9a"
ACCENT_CYAN = "#00f0ff"
ACCENT_MAGENTA = "#ff00aa"
ACCENT_PURPLE = "#8b5cf6"
SUCCESS = "#00ff88"
WARNING = "#ffaa00"
BUTTON_BG = "#1a1a2e"
BUTTON_HOVER = "#252545"
BUTTON_ACTIVE = "#0d0d12"

def style_button(btn, active=False):
    """Apply neon theme to a button."""
    if active:
        btn.config(bg=ACCENT_CYAN, fg=BG_DEEP,
                   activebackground=ACCENT_CYAN)
    else:
        btn.config(bg=BUTTON_BG, fg=TEXT_PRIMARY,
                   activebackground=BUTTON_HOVER)

def style_label(lbl, secondary=False):
    """Apply neon theme to a label."""
    fg = TEXT_SECONDARY if secondary else TEXT_PRIMARY
    lbl.config(fg=fg, bg=BG_PANEL)

def style_frame(frame):
    """Apply neon theme to a frame."""
    frame.config(bg=BG_PANEL)

def style_panel_header(lbl, accent_color=ACCENT_CYAN):
    """Style a section header with accent underline."""
    lbl.config(fg=accent_color, bg=BG_PANEL, font=("Consolas", 9, "bold"))
```

**Step 2:** Commit

```bash
git add src/ui/theme.py
git commit -m "feat: create neon retro theme system"
```

---

### Task 24: Apply theme to toolbar

**Files:**
- Modify: `src/ui/toolbar.py`

**Step 1:** Import theme and apply to all toolbar widgets

- Background: `BG_DEEP`
- Tool buttons: Use Unicode symbols + text, `BUTTON_BG` background
- Active tool: `ACCENT_CYAN` background with `BG_DEEP` text
- Size controls: themed buttons
- Separators: `BORDER` color
- Group tools with separators: Draw tools | Select tools | Navigate tools

Tool symbols:
```python
TOOL_SYMBOLS = {
    "Pen": "✎", "Eraser": "◌", "Blur": "◎", "Fill": "◆",
    "Ellipse": "◯", "Pick": "◉", "Select": "�default", "Wand": "✦",
    "Line": "╱", "Rect": "▭", "Hand": "✋",
}
```

**Step 2:** Commit

```bash
git add src/ui/toolbar.py
git commit -m "style: apply neon retro theme to toolbar"
```

---

### Task 25: Apply theme to right panel

**Files:**
- Modify: `src/ui/right_panel.py`

**Step 1:** Apply theme to all right panel components

- Panel background: `BG_PANEL`
- Section headers: `ACCENT_CYAN` with underline
- Palette swatches: subtle `BORDER` borders, selected = `ACCENT_CYAN` border
- Color picker: dark themed gradient, `ACCENT_MAGENTA` crosshair
- Layer panel: `ACCENT_CYAN` active indicator, eye icons for visibility
- Frame list: `ACCENT_CYAN` current frame highlight
- Animation preview: `BG_PANEL_ALT` background
- Compression stats: monospace font, `TEXT_SECONDARY` color
- All buttons: themed via `style_button()`
- All Listbox/Text widgets: `BG_PANEL_ALT` bg, `TEXT_PRIMARY` fg

**Step 2:** Commit

```bash
git add src/ui/right_panel.py
git commit -m "style: apply neon retro theme to right panel"
```

---

### Task 26: Apply theme to main app and dialogs

**Files:**
- Modify: `src/app.py`
- Modify: `src/ui/dialogs.py`

**Step 1:** Theme the main window

- Root background: `BG_DEEP`
- Canvas outer frame: `BG_PANEL_ALT`
- Menu bar: `BG_PANEL` bg, `TEXT_PRIMARY` fg, `ACCENT_CYAN` active
- Status bar: gradient-style with `BG_DEEP` bg, `ACCENT_CYAN` for key info, `TEXT_SECONDARY` for regular
- Scrollbars: `BG_PANEL_ALT` trough, `BUTTON_BG` slider

**Step 2:** Theme startup dialog

- Background: `BG_DEEP`
- Title "RetroSprite": `ACCENT_CYAN` with large font
- Subtitle: `TEXT_SECONDARY`
- Size buttons: `BUTTON_BG` with `ACCENT_CYAN` border on hover
- "Open Project" button: `ACCENT_MAGENTA` bg, bold
- Separator: `BORDER`

**Step 3:** Theme all other dialogs (canvas size, save-before, etc.)

**Step 4:** Manual visual test

Run: `python main.py`
Verify: Full neon retro aesthetic across startup, main editor, and all panels.

**Step 5:** Commit

```bash
git add src/app.py src/ui/dialogs.py
git commit -m "style: apply neon retro theme to main app and dialogs"
```

---

### Task 27: Final integration test

**Files:** None (testing only)

**Step 1:** Run full test suite

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 2:** Manual smoke test

Run: `python main.py`
Verify checklist:
- [ ] Startup dialog renders with neon theme
- [ ] Create new 32x32 canvas
- [ ] Draw with Pen tool on Layer 1
- [ ] Add Layer 2, draw different color
- [ ] Toggle layer visibility — lower layer shows/hides
- [ ] Change layer opacity — blending visible
- [ ] Ellipse tool draws correctly
- [ ] Symmetry mode mirrors drawing
- [ ] Magic wand selects contiguous area
- [ ] Dithering brush patterns work
- [ ] Shading ink lightens/darkens along palette
- [ ] Frame tags can be added
- [ ] Ping-pong playback works
- [ ] Sprite sheet export produces PNG + JSON
- [ ] Auto-save triggers after 60s of changes
- [ ] Reference image overlay loads and toggles
- [ ] All panels themed with neon retro colors
- [ ] Undo/redo works across layers

**Step 3:** Commit

```bash
git commit --allow-empty -m "chore: full overhaul integration verified"
```

---

## Summary

| Phase | Tasks | Key Deliverables |
|-------|-------|-----------------|
| 1. Foundation | 1-8 | NumPy backend, Layer model, delta undo, render optimization, layer panel UI |
| 2. Tools | 9-15 | Ellipse, symmetry, magic wand, pixel-perfect, dithering, shading ink, gradient fill |
| 3. Animation | 16-18 | Frame tags, playback modes, threaded GIF export |
| 4. QoL | 19-22 | Sprite sheet export, auto-save, custom shortcuts, reference overlay |
| 5. Visuals | 23-27 | Neon retro theme system, toolbar redesign, panel theming, dialog theming |

**Total:** 27 tasks across 5 phases.
