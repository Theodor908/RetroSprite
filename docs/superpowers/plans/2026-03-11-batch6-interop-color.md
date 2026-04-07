# Batch 6: Interop & Color Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add indexed color mode, color reduction, palette import/export (GPL/PAL/HEX/ASE), Aseprite file import, and PNG sequence export to RetroSprite.

**Architecture:** `IndexedPixelGrid` stores uint16 palette indices with PixelGrid-compatible `get_pixel`/`set_pixel` API (holds palette reference internally). Tools work transparently. Compositing always resolves to RGBA. Palette I/O and Aseprite import are standalone modules with no Tkinter dependency. Project format bumps to v4.

**Tech Stack:** Python 3.8+, NumPy, Pillow, struct (for ASE binary), zlib (for Aseprite), pytest

**Spec:** `docs/superpowers/specs/2026-03-11-batch6-interop-color-design.md`

**Note:** NO git commits — user explicitly wants no version control operations.

---

## Chunk 1: Core Data Layer (Tasks 1-4)

### Task 1: IndexedPixelGrid + nearest_palette_index

**Files:**
- Modify: `src/pixel_data.py`
- Create: `tests/test_interop_color.py`

- [ ] **Step 1: Write tests for nearest_palette_index and IndexedPixelGrid**

In `tests/test_interop_color.py`:

```python
"""Tests for Batch 6: Interop & Color features."""
import numpy as np
import pytest
from src.pixel_data import PixelGrid, IndexedPixelGrid, nearest_palette_index


class TestNearestPaletteIndex:
    def test_exact_match(self):
        palette = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]
        assert nearest_palette_index((0, 255, 0, 255), palette) == 1

    def test_nearest_color(self):
        palette = [(0, 0, 0, 255), (255, 255, 255, 255)]
        # (200,200,200) is closer to white
        assert nearest_palette_index((200, 200, 200, 255), palette) == 1

    def test_single_color_palette(self):
        palette = [(128, 128, 128, 255)]
        assert nearest_palette_index((0, 0, 0, 255), palette) == 0


class TestIndexedPixelGrid:
    def setup_method(self):
        self.palette = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]
        self.grid = IndexedPixelGrid(4, 4, self.palette)

    def test_init_all_transparent(self):
        assert self.grid.get_pixel(0, 0) == (0, 0, 0, 0)
        assert self.grid.get_index(0, 0) == 0

    def test_set_pixel_snaps_to_palette(self):
        self.grid.set_pixel(0, 0, (255, 0, 0, 255))  # exact red
        assert self.grid.get_index(0, 0) == 1  # 1-based
        assert self.grid.get_pixel(0, 0) == (255, 0, 0, 255)

    def test_set_pixel_transparent_sets_index_zero(self):
        self.grid.set_pixel(0, 0, (255, 0, 0, 255))
        self.grid.set_pixel(0, 0, (0, 0, 0, 0))
        assert self.grid.get_index(0, 0) == 0

    def test_set_pixel_snaps_nearest(self):
        # (200, 50, 50) is closest to red (255,0,0)
        self.grid.set_pixel(1, 1, (200, 50, 50, 255))
        assert self.grid.get_index(1, 1) == 1  # red

    def test_out_of_bounds_returns_none(self):
        assert self.grid.get_pixel(-1, 0) is None
        assert self.grid.get_pixel(0, 99) is None

    def test_to_rgba_vectorized(self):
        self.grid.set_pixel(0, 0, (255, 0, 0, 255))
        self.grid.set_pixel(1, 0, (0, 255, 0, 255))
        rgba = self.grid.to_rgba()
        assert rgba.shape == (4, 4, 4)
        assert tuple(rgba[0, 0]) == (255, 0, 0, 255)
        assert tuple(rgba[0, 1]) == (0, 255, 0, 255)
        assert tuple(rgba[1, 0]) == (0, 0, 0, 0)  # still transparent

    def test_to_pil_image(self):
        self.grid.set_pixel(0, 0, (255, 0, 0, 255))
        img = self.grid.to_pil_image()
        assert img.size == (4, 4)
        assert img.mode == "RGBA"

    def test_copy_preserves_data_and_palette(self):
        self.grid.set_pixel(0, 0, (255, 0, 0, 255))
        copy = self.grid.copy()
        assert copy.get_index(0, 0) == 1
        assert copy._palette is self.palette

    def test_extract_region(self):
        self.grid.set_pixel(1, 1, (0, 255, 0, 255))
        region = self.grid.extract_region(1, 1, 2, 2)
        assert region.width == 2
        assert region.height == 2
        assert region.get_index(0, 0) == 2  # green at (0,0) of region

    def test_paste_region(self):
        source = IndexedPixelGrid(2, 2, self.palette)
        source.set_index(0, 0, 3)  # blue
        self.grid.paste_region(source, 1, 1)
        assert self.grid.get_index(1, 1) == 3

    def test_clear(self):
        self.grid.set_pixel(0, 0, (255, 0, 0, 255))
        self.grid.clear()
        assert self.grid.get_index(0, 0) == 0

    def test_serialization_roundtrip(self):
        self.grid.set_pixel(0, 0, (255, 0, 0, 255))
        self.grid.set_pixel(1, 0, (0, 0, 255, 255))
        flat = self.grid.to_flat_indices()
        restored = IndexedPixelGrid.from_flat_indices(4, 4, flat, self.palette)
        assert restored.get_index(0, 0) == self.grid.get_index(0, 0)
        assert restored.get_index(1, 0) == self.grid.get_index(1, 0)

    def test_to_pixelgrid(self):
        self.grid.set_pixel(0, 0, (0, 255, 0, 255))
        pg = self.grid.to_pixelgrid()
        assert isinstance(pg, PixelGrid)
        assert pg.get_pixel(0, 0) == (0, 255, 0, 255)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_interop_color.py::TestNearestPaletteIndex -v --tb=short`
Expected: FAIL (ImportError — `nearest_palette_index` not found)

- [ ] **Step 3: Implement nearest_palette_index and IndexedPixelGrid**

Add to `src/pixel_data.py` (after the `PixelGrid` class, before EOF):

```python
def nearest_palette_index(color: tuple, palette: list[tuple]) -> int:
    """Find the palette index with minimum Euclidean RGB distance."""
    r, g, b = color[0], color[1], color[2]
    best_idx = 0
    best_dist = float('inf')
    for i, pc in enumerate(palette):
        dr = r - pc[0]
        dg = g - pc[1]
        db = b - pc[2]
        dist = dr * dr + dg * dg + db * db
        if dist < best_dist:
            best_dist = dist
            best_idx = i
    return best_idx


class IndexedPixelGrid:
    """A 2D grid of palette indices backed by a NumPy uint16 array."""

    def __init__(self, width: int, height: int, palette: list[tuple] | None = None):
        self.width = width
        self.height = height
        self._palette = palette or []
        self._indices = np.zeros((height, width), dtype=np.uint16)

    def get_pixel(self, x: int, y: int) -> tuple[int, int, int, int] | None:
        if 0 <= x < self.width and 0 <= y < self.height:
            idx = int(self._indices[y, x])
            if idx == 0:
                return (0, 0, 0, 0)
            if idx - 1 < len(self._palette):
                return self._palette[idx - 1]
            return (0, 0, 0, 0)
        return None

    def set_pixel(self, x: int, y: int, color: tuple[int, int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            if color[3] == 0:
                self._indices[y, x] = 0
                return
            idx = nearest_palette_index(color, self._palette)
            self._indices[y, x] = idx + 1

    def get_index(self, x: int, y: int) -> int | None:
        if 0 <= x < self.width and 0 <= y < self.height:
            return int(self._indices[y, x])
        return None

    def set_index(self, x: int, y: int, index: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self._indices[y, x] = index

    def to_rgba(self, palette: list[tuple] | None = None) -> np.ndarray:
        pal = palette or self._palette
        max_idx = len(pal)
        lut = np.zeros((max_idx + 1, 4), dtype=np.uint8)
        for i, color in enumerate(pal):
            lut[i + 1] = color
        safe_indices = np.clip(self._indices, 0, max_idx)
        return lut[safe_indices]

    def to_pil_image(self, palette: list[tuple] | None = None):
        from PIL import Image
        return Image.fromarray(self.to_rgba(palette), "RGBA")

    def to_pixelgrid(self, palette: list[tuple] | None = None) -> 'PixelGrid':
        grid = PixelGrid(self.width, self.height)
        grid._pixels = self.to_rgba(palette)
        return grid

    def copy(self) -> 'IndexedPixelGrid':
        new = IndexedPixelGrid(self.width, self.height, self._palette)
        new._indices = self._indices.copy()
        return new

    def clear(self) -> None:
        self._indices[:] = 0

    def extract_region(self, x: int, y: int, w: int, h: int) -> 'IndexedPixelGrid':
        region = IndexedPixelGrid(w, h, self._palette)
        for ry in range(h):
            for rx in range(w):
                sx, sy = x + rx, y + ry
                if 0 <= sx < self.width and 0 <= sy < self.height:
                    region._indices[ry, rx] = self._indices[sy, sx]
        return region

    def paste_region(self, source: 'IndexedPixelGrid', x: int, y: int) -> None:
        for sy in range(source.height):
            for sx in range(source.width):
                if source._indices[sy, sx] > 0:
                    tx, ty = x + sx, y + sy
                    if 0 <= tx < self.width and 0 <= ty < self.height:
                        self._indices[ty, tx] = source._indices[sy, sx]

    def to_flat_indices(self) -> list[int]:
        return self._indices.flatten().tolist()

    def to_flat_list(self) -> list[tuple[int, int, int, int]]:
        rgba = self.to_rgba()
        flat = rgba.reshape(-1, 4)
        return [tuple(int(v) for v in row) for row in flat]

    @classmethod
    def from_flat_indices(cls, width: int, height: int, indices: list[int],
                          palette: list[tuple] | None = None) -> 'IndexedPixelGrid':
        grid = cls(width, height, palette)
        grid._indices = np.array(indices, dtype=np.uint16).reshape(height, width)
        return grid
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_interop_color.py -v --tb=short`
Expected: ALL PASS

---

### Task 2: Layer color_mode + flatten_layers indexed support

**Files:**
- Modify: `src/layer.py`
- Test: `tests/test_interop_color.py`

- [ ] **Step 1: Write tests for indexed layer**

Append to `tests/test_interop_color.py`:

```python
from src.layer import Layer, flatten_layers


class TestIndexedLayer:
    def setup_method(self):
        self.palette = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]

    def test_layer_default_is_rgba(self):
        layer = Layer("test", 4, 4)
        assert layer.color_mode == "rgba"
        assert isinstance(layer.pixels, PixelGrid)

    def test_layer_indexed_mode(self):
        layer = Layer("test", 4, 4, color_mode="indexed", palette=self.palette)
        assert layer.color_mode == "indexed"
        assert isinstance(layer.pixels, IndexedPixelGrid)

    def test_indexed_layer_set_get_pixel(self):
        layer = Layer("test", 4, 4, color_mode="indexed", palette=self.palette)
        layer.pixels.set_pixel(0, 0, (255, 0, 0, 255))
        assert layer.pixels.get_pixel(0, 0) == (255, 0, 0, 255)

    def test_indexed_layer_copy(self):
        layer = Layer("test", 4, 4, color_mode="indexed", palette=self.palette)
        layer.pixels.set_pixel(0, 0, (0, 255, 0, 255))
        copy = layer.copy()
        assert copy.color_mode == "indexed"
        assert isinstance(copy.pixels, IndexedPixelGrid)
        assert copy.pixels.get_pixel(0, 0) == (0, 255, 0, 255)

    def test_flatten_indexed_layer(self):
        layer = Layer("bg", 4, 4, color_mode="indexed", palette=self.palette)
        layer.pixels.set_pixel(0, 0, (255, 0, 0, 255))
        result = flatten_layers([layer], 4, 4)
        assert isinstance(result, PixelGrid)
        assert result.get_pixel(0, 0) == (255, 0, 0, 255)

    def test_flatten_mixed_rgba_and_indexed(self):
        rgba_layer = Layer("bg", 4, 4)
        rgba_layer.pixels.set_pixel(0, 0, (128, 128, 128, 255))
        idx_layer = Layer("fg", 4, 4, color_mode="indexed", palette=self.palette)
        idx_layer.pixels.set_pixel(1, 0, (0, 0, 255, 255))
        result = flatten_layers([rgba_layer, idx_layer], 4, 4)
        assert result.get_pixel(0, 0) == (128, 128, 128, 255)  # from rgba
        assert result.get_pixel(1, 0) == (0, 0, 255, 255)  # from indexed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_interop_color.py::TestIndexedLayer -v --tb=short`
Expected: FAIL

- [ ] **Step 3: Modify Layer class**

In `src/layer.py`, update the import at top:
```python
from src.pixel_data import PixelGrid, IndexedPixelGrid
```

Update `Layer.__init__` (line 11-20):
```python
class Layer:
    def __init__(self, name: str, width: int, height: int,
                 color_mode: str = "rgba", palette: list[tuple] | None = None):
        self.name = name
        self.color_mode = color_mode
        if color_mode == "indexed":
            self.pixels = IndexedPixelGrid(width, height, palette)
        else:
            self.pixels = PixelGrid(width, height)
        self.visible: bool = True
        self.opacity: float = 1.0
        self.blend_mode: str = "normal"
        self.locked: bool = False
        self.depth: int = 0
        self.is_group: bool = False
        self.effects: list = []
```

Update `Layer.from_grid()` (line 22-26) to detect indexed grids:
```python
    @classmethod
    def from_grid(cls, name: str, grid) -> Layer:
        if hasattr(grid, '_indices'):
            layer = cls(name, grid.width, grid.height,
                        color_mode="indexed", palette=grid._palette)
            layer.pixels = grid.copy()
        else:
            layer = cls(name, grid.width, grid.height)
            layer.pixels._pixels = grid._pixels.copy()
        return layer
```

Update `Layer.copy()` (line 28-39):
```python
    def copy(self) -> Layer:
        palette = self.pixels._palette if self.color_mode == "indexed" else None
        new_layer = Layer(f"{self.name} Copy", self.pixels.width, self.pixels.height,
                          color_mode=self.color_mode, palette=palette)
        if self.color_mode == "indexed":
            new_layer.pixels = self.pixels.copy()
        else:
            new_layer.pixels._pixels = self.pixels._pixels.copy()
        new_layer.visible = self.visible
        new_layer.opacity = self.opacity
        new_layer.blend_mode = self.blend_mode
        new_layer.locked = self.locked
        new_layer.depth = self.depth
        new_layer.is_group = self.is_group
        import copy as copy_mod
        new_layer.effects = copy_mod.deepcopy(self.effects)
        return new_layer
```

Update `flatten_layers` — replace the pixel resolution block (lines ~144-156) with indexed-aware version:

```python
        # Resolve pixel data to RGBA
        if hasattr(layer.pixels, '_indices'):
            layer_rgba = layer.pixels.to_rgba()
        else:
            layer_rgba = layer.pixels._pixels

        if hasattr(layer, 'effects') and layer.effects:
            from src.effects import apply_effects
            raw = layer_rgba.copy()
            original_alpha = raw[:, :, 3].copy()
            processed = apply_effects(raw, layer.effects, original_alpha)
            layer_img = Image.fromarray(processed, "RGBA")
        else:
            layer_img = Image.fromarray(layer_rgba, "RGBA")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_interop_color.py -v --tb=short`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All existing tests still pass (344+)

---

### Task 3: AnimationTimeline color_mode + Frame indexed support

**Files:**
- Modify: `src/animation.py`
- Test: `tests/test_interop_color.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_interop_color.py`:

```python
from src.animation import AnimationTimeline, Frame


class TestTimelineIndexedMode:
    def setup_method(self):
        self.palette = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]

    def test_default_color_mode_is_rgba(self):
        tl = AnimationTimeline(8, 8)
        assert tl.color_mode == "rgba"

    def test_set_indexed_mode(self):
        tl = AnimationTimeline(8, 8)
        tl.color_mode = "indexed"
        tl.palette_ref = self.palette
        assert tl.color_mode == "indexed"

    def test_add_frame_respects_color_mode(self):
        tl = AnimationTimeline(8, 8)
        tl.color_mode = "indexed"
        tl.palette_ref = self.palette
        tl.add_frame()
        # New frame's first layer should be indexed
        frame = tl.get_frame_obj(tl.frame_count - 1)
        assert frame.layers[0].color_mode == "indexed"

    def test_add_layer_to_all_respects_color_mode(self):
        tl = AnimationTimeline(8, 8)
        tl.color_mode = "indexed"
        tl.palette_ref = self.palette
        tl.add_layer_to_all("New Layer")
        for i in range(tl.frame_count):
            frame = tl.get_frame_obj(i)
            new_layer = frame.layers[-1]
            assert new_layer.color_mode == "indexed"

    def test_frame_init_indexed(self):
        frame = Frame(8, 8, color_mode="indexed", palette=self.palette)
        assert frame.layers[0].color_mode == "indexed"

    def test_frame_add_layer_indexed(self):
        frame = Frame(8, 8, color_mode="indexed", palette=self.palette)
        layer = frame.add_layer("Layer 2")
        assert layer.color_mode == "indexed"
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement**

In `src/animation.py`:

Update `Frame.__init__` to accept color_mode/palette:
```python
class Frame:
    def __init__(self, width: int, height: int, name: str = "",
                 color_mode: str = "rgba", palette: list[tuple] | None = None):
        self.width = width
        self.height = height
        self.name = name
        self.color_mode = color_mode
        self._palette = palette
        self.layers: list[Layer] = [Layer("Layer 1", width, height,
                                          color_mode=color_mode, palette=palette)]
        self.active_layer_index: int = 0
        self.duration_ms: int = 100
```

Update `Frame.add_layer`:
```python
    def add_layer(self, name: str | None = None) -> Layer:
        if name is None:
            name = f"Layer {len(self.layers) + 1}"
        layer = Layer(name, self.width, self.height,
                      color_mode=self.color_mode, palette=self._palette)
        self.layers.append(layer)
        self.active_layer_index = len(self.layers) - 1
        return layer
```

Add `color_mode` and `palette_ref` to `AnimationTimeline.__init__` (after existing attrs):
```python
        self.color_mode: str = "rgba"
        self.palette_ref: list[tuple] | None = None
```

Update `AnimationTimeline.add_frame` — pass color_mode to Frame and to new layers:
In the `Frame()` constructor call, add `color_mode=self.color_mode, palette=self.palette_ref`.
In the `new_frame.add_layer()` call path, it will inherit from Frame's color_mode.

Update `AnimationTimeline.insert_frame` — same pattern.

Update `AnimationTimeline.add_layer_to_all`:
```python
    def add_layer_to_all(self, name: str | None = None) -> None:
        if not self._frames:
            return
        if name is None:
            name = f"Layer {len(self._frames[0].layers) + 1}"
        for frame in self._frames:
            layer = Layer(name, self.width, self.height,
                          color_mode=self.color_mode, palette=self.palette_ref)
            frame.layers.append(layer)
            frame.active_layer_index = len(frame.layers) - 1
```

Update `sync_layers` — in the `else` branch (line 142), pass color_mode:
```python
                    new_layer = Layer(ref_layer.name, self.width, self.height,
                                      color_mode=self.color_mode, palette=self.palette_ref)
```

Update `Frame.copy()` (line 89-94) to preserve color_mode/palette:
```python
    def copy(self) -> Frame:
        new_frame = Frame(self.width, self.height, name=f"{self.name} Copy" if self.name else "",
                          color_mode=self.color_mode, palette=self._palette)
        new_frame.layers = [layer.copy() for layer in self.layers]
        new_frame.active_layer_index = self.active_layer_index
        new_frame.duration_ms = self.duration_ms
        return new_frame
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

---

### Task 4: Project v4 — indexed serialization

**Files:**
- Modify: `src/project.py`
- Test: `tests/test_interop_color.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_interop_color.py`:

```python
import tempfile, os
from src.project import save_project, load_project
from src.palette import Palette


class TestProjectV4:
    def test_save_load_indexed_project(self):
        palette = Palette("Pico-8")
        tl = AnimationTimeline(4, 4)
        tl.color_mode = "indexed"
        tl.palette_ref = palette.colors
        # Replace first frame's layer with indexed
        frame = tl.get_frame_obj(0)
        frame.layers[0] = Layer("Layer 1", 4, 4, color_mode="indexed", palette=palette.colors)
        frame.layers[0].pixels.set_pixel(0, 0, palette.colors[0])

        with tempfile.NamedTemporaryFile(suffix=".retro", delete=False) as f:
            path = f.name
        try:
            save_project(path, tl, palette)
            tl2, pal2 = load_project(path)
            assert tl2.color_mode == "indexed"
            layer = tl2.get_frame_obj(0).layers[0]
            assert layer.color_mode == "indexed"
            assert isinstance(layer.pixels, IndexedPixelGrid)
            assert layer.pixels.get_index(0, 0) == 1  # first palette color
        finally:
            os.unlink(path)

    def test_v3_loads_as_rgba(self):
        """Existing v3 files should load as rgba mode."""
        palette = Palette("Pico-8")
        tl = AnimationTimeline(4, 4)
        # Save as v3 (default rgba mode)
        with tempfile.NamedTemporaryFile(suffix=".retro", delete=False) as f:
            path = f.name
        try:
            save_project(path, tl, palette)
            tl2, pal2 = load_project(path)
            assert tl2.color_mode == "rgba"
        finally:
            os.unlink(path)
```

- [ ] **Step 2: Implement v4 serialization**

In `src/project.py`:

Add import at top:
```python
from src.pixel_data import PixelGrid, IndexedPixelGrid
```

In `save_project`, update version to 4 when color_mode is indexed. Add `color_mode` to project dict:
```python
    project = {
        "version": 4 if getattr(timeline, 'color_mode', 'rgba') == 'indexed' else 3,
        "color_mode": getattr(timeline, 'color_mode', 'rgba'),
        ...
    }
```

In the layer serialization loop, for indexed layers add `"indices"` instead of `"pixels"`:
```python
            if layer.color_mode == "indexed":
                layers_data.append({
                    "name": layer.name,
                    "color_mode": "indexed",
                    "indices": layer.pixels.to_flat_indices(),
                    "visible": layer.visible,
                    "opacity": layer.opacity,
                    "blend_mode": layer.blend_mode,
                    "locked": layer.locked,
                    "depth": layer.depth,
                    "is_group": getattr(layer, 'is_group', False),
                    "effects": [fx.to_dict() for fx in getattr(layer, 'effects', [])],
                })
                continue
```

**CRITICAL: In `load_project`, load palette BEFORE the frames loop.** Currently palette is loaded at the bottom (after frames). Move it up so indexed layers can reference it:

```python
    # --- Load palette FIRST (needed for indexed layers) ---
    palette_name = project.get("palette_name", "Pico-8")
    palette = Palette(palette_name)
    if "palette_colors" in project:
        palette.colors = [tuple(c) for c in project["palette_colors"]]
    if "selected_color_index" in project:
        palette.select(project["selected_color_index"])

    # Set color_mode on timeline
    timeline.color_mode = project.get("color_mode", "rgba")
    if timeline.color_mode == "indexed":
        timeline.palette_ref = palette.colors
```

Then in the frames loop, for indexed layers:
```python
                if layer_data.get("color_mode") == "indexed":
                    layer = Layer(layer_data["name"], w, h, color_mode="indexed",
                                  palette=palette.colors)
                    layer.pixels = IndexedPixelGrid.from_flat_indices(
                        w, h, layer_data["indices"], palette.colors)
                else:
                    layer = Layer(layer_data["name"], w, h)
                    # ... existing pixel loading ...
                # Common attributes for both:
                layer.visible = layer_data.get("visible", True)
                layer.opacity = layer_data.get("opacity", 1.0)
                layer.blend_mode = layer_data.get("blend_mode", "normal")
                layer.locked = layer_data.get("locked", False)
                layer.depth = layer_data.get("depth", 0)
                layer.is_group = layer_data.get("is_group", False)
                from src.effects import LayerEffect
                layer.effects = [LayerEffect.from_dict(e) for e in layer_data.get("effects", [])]
```

**Remove** the palette loading code that currently sits at the bottom of `load_project` (lines 180-185) since it's now above the frames loop.

At the end of `load_project`, return `timeline, palette` as before.

- [ ] **Step 3: Run all tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

---

## Chunk 2: Quantization + Palette I/O (Tasks 5-7)

### Task 5: Median cut quantization

**Files:**
- Create: `src/quantize.py`
- Test: `tests/test_interop_color.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_interop_color.py`:

```python
from src.quantize import median_cut, quantize_to_palette


class TestMedianCut:
    def test_reduces_to_target_count(self):
        # 100 random colors → reduce to 4
        rng = np.random.RandomState(42)
        pixels = rng.randint(0, 256, (100, 4), dtype=np.uint8)
        pixels[:, 3] = 255  # all opaque
        result = median_cut(pixels, 4)
        assert len(result) == 4
        assert all(len(c) == 4 for c in result)

    def test_skips_transparent_pixels(self):
        pixels = np.array([
            [255, 0, 0, 255],
            [0, 0, 0, 0],     # transparent — skip
            [0, 255, 0, 255],
        ], dtype=np.uint8)
        result = median_cut(pixels, 2)
        assert len(result) == 2

    def test_single_color(self):
        pixels = np.array([[100, 100, 100, 255]] * 10, dtype=np.uint8)
        result = median_cut(pixels, 1)
        assert len(result) == 1
        r, g, b, a = result[0]
        assert abs(r - 100) < 2 and abs(g - 100) < 2

    def test_two_distinct_clusters(self):
        red = np.array([[255, 0, 0, 255]] * 50, dtype=np.uint8)
        blue = np.array([[0, 0, 255, 255]] * 50, dtype=np.uint8)
        pixels = np.vstack([red, blue])
        result = median_cut(pixels, 2)
        # Should produce one reddish and one bluish color
        reds = [c for c in result if c[0] > 128]
        blues = [c for c in result if c[2] > 128]
        assert len(reds) >= 1
        assert len(blues) >= 1


class TestQuantizeTopalette:
    def test_quantize_pixelgrid(self):
        grid = PixelGrid(2, 2)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        grid.set_pixel(1, 0, (0, 255, 0, 255))
        grid.set_pixel(0, 1, (0, 0, 255, 255))
        # (1,1) stays transparent
        palette = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]
        indexed = quantize_to_palette(grid, palette)
        assert isinstance(indexed, IndexedPixelGrid)
        assert indexed.get_index(0, 0) == 1  # red
        assert indexed.get_index(1, 0) == 2  # green
        assert indexed.get_index(0, 1) == 3  # blue
        assert indexed.get_index(1, 1) == 0  # transparent
```

- [ ] **Step 2: Implement**

Create `src/quantize.py`:

```python
"""Color reduction via median cut algorithm."""
from __future__ import annotations
import numpy as np
from src.pixel_data import PixelGrid, IndexedPixelGrid, nearest_palette_index


def median_cut(pixels: np.ndarray, num_colors: int) -> list[tuple[int, int, int, int]]:
    """Reduce colors using median cut algorithm.

    Args:
        pixels: (N, 4) uint8 array of RGBA pixels.
        num_colors: Target palette size (1-256).
    Returns:
        List of RGBA color tuples.
    """
    num_colors = max(1, min(256, num_colors))
    # Filter out transparent pixels
    opaque = pixels[pixels[:, 3] > 0]
    if len(opaque) == 0:
        return [(0, 0, 0, 255)] * num_colors

    rgb = opaque[:, :3].astype(np.int32)

    boxes = [rgb]
    while len(boxes) < num_colors:
        # Find box with largest range to split
        best_box_idx = 0
        best_range = -1
        best_channel = 0
        for i, box in enumerate(boxes):
            if len(box) < 2:
                continue
            for ch in range(3):
                r = box[:, ch].max() - box[:, ch].min()
                if r > best_range:
                    best_range = r
                    best_box_idx = i
                    best_channel = ch
        if best_range <= 0:
            break
        box = boxes.pop(best_box_idx)
        median = int(np.median(box[:, best_channel]))
        left = box[box[:, best_channel] <= median]
        right = box[box[:, best_channel] > median]
        if len(left) == 0:
            left = box[:1]
            right = box[1:]
        elif len(right) == 0:
            left = box[:-1]
            right = box[-1:]
        boxes.append(left)
        boxes.append(right)

    result = []
    for box in boxes:
        mean = box.mean(axis=0).astype(np.uint8)
        result.append((int(mean[0]), int(mean[1]), int(mean[2]), 255))

    # Pad if we got fewer than requested
    while len(result) < num_colors:
        result.append(result[-1] if result else (0, 0, 0, 255))

    return result[:num_colors]


def quantize_to_palette(grid: PixelGrid, palette: list[tuple]) -> IndexedPixelGrid:
    """Map each pixel to nearest palette color, return IndexedPixelGrid."""
    indexed = IndexedPixelGrid(grid.width, grid.height, palette)
    for y in range(grid.height):
        for x in range(grid.width):
            color = grid.get_pixel(x, y)
            if color and color[3] > 0:
                idx = nearest_palette_index(color, palette)
                indexed.set_index(x, y, idx + 1)
    return indexed
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_interop_color.py -v --tb=short`
Expected: ALL PASS

---

### Task 6: Palette I/O (GPL, PAL, HEX, ASE)

**Files:**
- Create: `src/palette_io.py`
- Test: `tests/test_interop_color.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_interop_color.py`:

```python
from src.palette_io import load_palette, save_palette


class TestPaletteIO:
    def setup_method(self):
        self.colors = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]

    def test_gpl_roundtrip(self):
        with tempfile.NamedTemporaryFile(suffix=".gpl", delete=False, mode="w") as f:
            path = f.name
        try:
            save_palette(path, self.colors, name="Test")
            loaded = load_palette(path)
            assert loaded == self.colors
        finally:
            os.unlink(path)

    def test_pal_roundtrip(self):
        with tempfile.NamedTemporaryFile(suffix=".pal", delete=False, mode="w") as f:
            path = f.name
        try:
            save_palette(path, self.colors)
            loaded = load_palette(path)
            assert loaded == self.colors
        finally:
            os.unlink(path)

    def test_hex_roundtrip(self):
        with tempfile.NamedTemporaryFile(suffix=".hex", delete=False, mode="w") as f:
            path = f.name
        try:
            save_palette(path, self.colors)
            loaded = load_palette(path)
            assert loaded == self.colors
        finally:
            os.unlink(path)

    def test_ase_roundtrip(self):
        with tempfile.NamedTemporaryFile(suffix=".ase", delete=False, mode="wb") as f:
            path = f.name
        try:
            save_palette(path, self.colors, name="Test")
            loaded = load_palette(path)
            # ASE uses floats, so allow small rounding differences
            for orig, loaded_c in zip(self.colors, loaded):
                for i in range(3):
                    assert abs(orig[i] - loaded_c[i]) <= 1
        finally:
            os.unlink(path)

    def test_hex_format_no_hash(self):
        with tempfile.NamedTemporaryFile(suffix=".hex", delete=False, mode="w") as f:
            path = f.name
        try:
            save_palette(path, [(255, 0, 0, 255)])
            with open(path) as f:
                content = f.read().strip()
            assert content == "ff0000"
        finally:
            os.unlink(path)

    def test_load_hex_with_hash(self):
        """Load should handle # prefix gracefully."""
        with tempfile.NamedTemporaryFile(suffix=".hex", delete=False, mode="w") as f:
            f.write("#ff0000\n#00ff00\n")
            path = f.name
        try:
            loaded = load_palette(path)
            assert loaded[0] == (255, 0, 0, 255)
            assert loaded[1] == (0, 255, 0, 255)
        finally:
            os.unlink(path)
```

- [ ] **Step 2: Implement**

Create `src/palette_io.py`:

```python
"""Palette file import/export — GPL, PAL, HEX, ASE formats."""
from __future__ import annotations
import struct
import os


def load_palette(path: str) -> list[tuple[int, int, int, int]]:
    """Auto-detect format from extension and load palette colors."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".gpl":
        return _load_gpl(path)
    elif ext == ".pal":
        return _load_pal(path)
    elif ext == ".hex":
        return _load_hex(path)
    elif ext == ".ase":
        return _load_ase(path)
    else:
        raise ValueError(f"Unsupported palette format: {ext}")


def save_palette(path: str, colors: list[tuple[int, int, int, int]],
                 name: str = "Untitled") -> None:
    """Save palette in format matching extension."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".gpl":
        _save_gpl(path, colors, name)
    elif ext == ".pal":
        _save_pal(path, colors)
    elif ext == ".hex":
        _save_hex(path, colors)
    elif ext == ".ase":
        _save_ase(path, colors, name)
    else:
        raise ValueError(f"Unsupported palette format: {ext}")


# --- GPL (GIMP Palette) ---

def _load_gpl(path: str) -> list[tuple[int, int, int, int]]:
    colors = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("GIMP") or line.startswith("Name:") or line.startswith("Columns:"):
                continue
            parts = line.split()
            if len(parts) >= 3:
                try:
                    r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                    colors.append((r, g, b, 255))
                except ValueError:
                    continue
    return colors


def _save_gpl(path: str, colors: list[tuple], name: str) -> None:
    with open(path, "w") as f:
        f.write(f"GIMP Palette\nName: {name}\n#\n")
        for i, c in enumerate(colors):
            f.write(f"{c[0]:3d} {c[1]:3d} {c[2]:3d}\tcolor_{i}\n")


# --- PAL (JASC-PAL) ---

def _load_pal(path: str) -> list[tuple[int, int, int, int]]:
    colors = []
    with open(path, "r") as f:
        lines = f.read().strip().split("\n")
    # Skip header: JASC-PAL, 0100, count
    if len(lines) < 3:
        return colors
    for line in lines[3:]:
        parts = line.strip().split()
        if len(parts) >= 3:
            try:
                r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                colors.append((r, g, b, 255))
            except ValueError:
                continue
    return colors


def _save_pal(path: str, colors: list[tuple]) -> None:
    with open(path, "w") as f:
        f.write("JASC-PAL\n0100\n")
        f.write(f"{len(colors)}\n")
        for c in colors:
            f.write(f"{c[0]} {c[1]} {c[2]}\n")


# --- HEX (Lospec) ---

def _load_hex(path: str) -> list[tuple[int, int, int, int]]:
    colors = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip().lstrip("#")
            if len(line) >= 6:
                try:
                    r = int(line[0:2], 16)
                    g = int(line[2:4], 16)
                    b = int(line[4:6], 16)
                    colors.append((r, g, b, 255))
                except ValueError:
                    continue
    return colors


def _save_hex(path: str, colors: list[tuple]) -> None:
    with open(path, "w") as f:
        for c in colors:
            f.write(f"{c[0]:02x}{c[1]:02x}{c[2]:02x}\n")


# --- ASE (Adobe Swatch Exchange) ---

def _load_ase(path: str) -> list[tuple[int, int, int, int]]:
    colors = []
    with open(path, "rb") as f:
        magic = f.read(4)
        if magic != b"ASEF":
            raise ValueError("Not a valid ASE file")
        _version = struct.unpack(">HH", f.read(4))
        block_count = struct.unpack(">I", f.read(4))[0]
        for _ in range(block_count):
            block_type = struct.unpack(">H", f.read(2))[0]
            block_size = struct.unpack(">I", f.read(4))[0]
            block_data = f.read(block_size)
            if block_type == 0x0001:  # Color entry
                offset = 0
                name_len = struct.unpack(">H", block_data[offset:offset+2])[0]
                offset += 2 + name_len * 2  # UTF-16 chars
                model = block_data[offset:offset+4]
                offset += 4
                if model == b"RGB ":
                    rf, gf, bf = struct.unpack(">fff", block_data[offset:offset+12])
                    r = max(0, min(255, round(rf * 255)))
                    g = max(0, min(255, round(gf * 255)))
                    b = max(0, min(255, round(bf * 255)))
                    colors.append((r, g, b, 255))
    return colors


def _save_ase(path: str, colors: list[tuple], name: str) -> None:
    blocks = []
    for i, c in enumerate(colors):
        color_name = f"color_{i}"
        name_encoded = color_name.encode("utf-16-be") + b"\x00\x00"
        name_len = len(color_name) + 1  # +1 for null terminator
        rf = c[0] / 255.0
        gf = c[1] / 255.0
        bf = c[2] / 255.0
        block_data = struct.pack(">H", name_len)
        block_data += name_encoded
        block_data += b"RGB "
        block_data += struct.pack(">fff", rf, gf, bf)
        block_data += struct.pack(">H", 0)  # color type: global
        blocks.append(block_data)

    with open(path, "wb") as f:
        f.write(b"ASEF")
        f.write(struct.pack(">HH", 1, 0))  # version 1.0
        f.write(struct.pack(">I", len(blocks)))
        for block_data in blocks:
            f.write(struct.pack(">H", 0x0001))  # color entry
            f.write(struct.pack(">I", len(block_data)))
            f.write(block_data)
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_interop_color.py::TestPaletteIO -v --tb=short`
Expected: ALL PASS

---

### Task 7: Conversion functions (RGBA ↔ Indexed)

**Files:**
- Modify: `src/scripting.py`
- Test: `tests/test_interop_color.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_interop_color.py`:

```python
from src.scripting import RetroSpriteAPI


class TestConversion:
    def test_convert_to_indexed(self):
        palette = Palette("Pico-8")
        tl = AnimationTimeline(4, 4)
        # Paint a pixel
        tl.get_frame_obj(0).layers[0].pixels.set_pixel(0, 0, (255, 0, 77, 255))
        api = RetroSpriteAPI(timeline=tl, palette=palette, app=None)
        api.convert_to_indexed()
        assert tl.color_mode == "indexed"
        layer = tl.get_frame_obj(0).layers[0]
        assert layer.color_mode == "indexed"
        assert isinstance(layer.pixels, IndexedPixelGrid)
        # Pixel should be snapped to nearest Pico-8 color
        assert layer.pixels.get_index(0, 0) > 0

    def test_convert_to_rgba(self):
        palette = Palette("Pico-8")
        tl = AnimationTimeline(4, 4)
        tl.color_mode = "indexed"
        tl.palette_ref = palette.colors
        frame = tl.get_frame_obj(0)
        frame.layers[0] = Layer("Layer 1", 4, 4, color_mode="indexed", palette=palette.colors)
        frame.layers[0].pixels.set_pixel(0, 0, palette.colors[0])
        api = RetroSpriteAPI(timeline=tl, palette=palette, app=None)
        api.convert_to_rgba()
        assert tl.color_mode == "rgba"
        layer = tl.get_frame_obj(0).layers[0]
        assert layer.color_mode == "rgba"
        assert isinstance(layer.pixels, PixelGrid)

    def test_convert_to_indexed_with_num_colors(self):
        palette = Palette("Pico-8")
        tl = AnimationTimeline(4, 4)
        tl.get_frame_obj(0).layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))
        tl.get_frame_obj(0).layers[0].pixels.set_pixel(1, 0, (0, 0, 255, 255))
        api = RetroSpriteAPI(timeline=tl, palette=palette, app=None)
        api.convert_to_indexed(num_colors=4)
        assert len(palette.colors) == 4
        assert tl.color_mode == "indexed"
```

- [ ] **Step 2: Implement**

Add to `src/scripting.py` (as methods on `RetroSpriteAPI`):

```python
    def convert_to_indexed(self, num_colors: int | None = None) -> None:
        """Convert project from RGBA to indexed color mode."""
        from src.quantize import median_cut, quantize_to_palette
        from src.pixel_data import IndexedPixelGrid

        if num_colors is not None:
            # Gather all pixels for median cut
            all_pixels = []
            for i in range(self.timeline.frame_count):
                frame = self.timeline.get_frame_obj(i)
                for layer in frame.layers:
                    if hasattr(layer, 'is_tilemap') and layer.is_tilemap():
                        continue
                    if layer.color_mode == "indexed":
                        continue
                    all_pixels.append(layer.pixels._pixels.reshape(-1, 4))
            if all_pixels:
                combined = np.vstack(all_pixels)
                new_colors = median_cut(combined, num_colors)
                self.palette.colors.clear()
                self.palette.colors.extend(new_colors)

        palette_colors = self.palette.colors
        self.timeline.palette_ref = palette_colors
        for i in range(self.timeline.frame_count):
            frame = self.timeline.get_frame_obj(i)
            for j, layer in enumerate(frame.layers):
                if hasattr(layer, 'is_tilemap') and layer.is_tilemap():
                    continue
                if layer.color_mode == "indexed":
                    continue
                indexed = quantize_to_palette(layer.pixels, palette_colors)
                layer.pixels = indexed
                layer.color_mode = "indexed"
        self.timeline.color_mode = "indexed"

    def convert_to_rgba(self) -> None:
        """Convert project from indexed to RGBA color mode."""
        palette_colors = self.palette.colors
        for i in range(self.timeline.frame_count):
            frame = self.timeline.get_frame_obj(i)
            for j, layer in enumerate(frame.layers):
                if hasattr(layer, 'is_tilemap') and layer.is_tilemap():
                    continue
                if layer.color_mode != "indexed":
                    continue
                rgba_grid = layer.pixels.to_pixelgrid(palette_colors)
                layer.pixels = rgba_grid
                layer.color_mode = "rgba"
        self.timeline.color_mode = "rgba"
        self.timeline.palette_ref = None
```

Add `import numpy as np` at top of scripting.py if not present.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_interop_color.py -v --tb=short`
Expected: ALL PASS

---

## Chunk 3: Aseprite Import + PNG Sequence Export (Tasks 8-10)

### Task 8: PNG Sequence Export

**Files:**
- Modify: `src/export.py`
- Test: `tests/test_interop_color.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_interop_color.py`:

```python
from src.export import export_png_sequence


class TestPNGSequenceExport:
    def test_exports_correct_number_of_files(self):
        tl = AnimationTimeline(4, 4)
        tl.add_frame()  # now 2 frames
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "sprite.png")
            paths = export_png_sequence(tl, out)
            assert len(paths) == 2
            assert all(os.path.exists(p) for p in paths)
            assert paths[0].endswith("sprite_000.png")
            assert paths[1].endswith("sprite_001.png")

    def test_scale_factor(self):
        tl = AnimationTimeline(4, 4)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "sprite.png")
            paths = export_png_sequence(tl, out, scale=2)
            from PIL import Image
            img = Image.open(paths[0])
            assert img.size == (8, 8)

    def test_single_frame(self):
        tl = AnimationTimeline(4, 4)
        tl.get_frame_obj(0).layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "test.png")
            paths = export_png_sequence(tl, out)
            assert len(paths) == 1
            from PIL import Image
            img = Image.open(paths[0])
            assert img.getpixel((0, 0)) == (255, 0, 0, 255)
```

- [ ] **Step 2: Implement**

Add to `src/export.py`:

```python
import os

def export_png_sequence(timeline, output_path: str, scale: int = 1,
                        layer=None) -> list[str]:
    """Export each frame as a numbered PNG file."""
    base, ext = os.path.splitext(output_path)
    if not ext:
        ext = ".png"
    paths = []
    for i in range(timeline.frame_count):
        if layer is not None:
            frame_obj = timeline.get_frame_obj(i)
            if isinstance(layer, str):
                target = next((l for l in frame_obj.layers if l.name == layer), None)
            else:
                target = frame_obj.layers[layer] if 0 <= layer < len(frame_obj.layers) else None
            if target:
                img = target.pixels.to_pil_image()
            else:
                img = Image.new("RGBA", (timeline.width, timeline.height), (0, 0, 0, 0))
        else:
            grid = timeline.get_frame(i)
            img = grid.to_pil_image()
        if scale > 1:
            img = img.resize((timeline.width * scale, timeline.height * scale), Image.NEAREST)
        frame_path = f"{base}_{i:03d}{ext}"
        img.save(frame_path)
        paths.append(frame_path)
    return paths
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_interop_color.py::TestPNGSequenceExport -v --tb=short`
Expected: ALL PASS

---

### Task 9: Aseprite import

**Files:**
- Create: `src/aseprite_import.py`
- Test: `tests/test_interop_color.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_interop_color.py`:

```python
from src.aseprite_import import load_aseprite, ASE_BLEND_MAP


class TestAsepriteImport:
    def test_blend_map_has_standard_modes(self):
        assert ASE_BLEND_MAP[0] == "normal"
        assert ASE_BLEND_MAP[1] == "multiply"
        assert ASE_BLEND_MAP[2] == "screen"
        assert ASE_BLEND_MAP.get(6, "normal") == "normal"  # unsupported fallback

    def test_load_minimal_ase_file(self):
        """Create a minimal valid .ase file in memory and parse it."""
        import struct, zlib
        # Build a minimal Aseprite file: 4x4, 1 frame, 1 layer, RGBA
        # Header (128 bytes)
        header = bytearray(128)
        struct.pack_into("<I", header, 0, 0)      # file size (fill later)
        struct.pack_into("<H", header, 4, 0xA5E0)  # magic
        struct.pack_into("<H", header, 6, 1)       # frame count
        struct.pack_into("<H", header, 8, 4)       # width
        struct.pack_into("<H", header, 10, 4)      # height
        struct.pack_into("<H", header, 12, 32)     # color depth (RGBA)
        struct.pack_into("<I", header, 14, 1)      # flags
        struct.pack_into("<H", header, 18, 100)    # speed (ms)
        # Palette entry count at offset 28
        struct.pack_into("<I", header, 28, 0)

        # Frame header
        frame_chunks = bytearray()

        # Layer chunk (0x2004)
        layer_data = bytearray()
        layer_data += struct.pack("<H", 1)        # flags (visible)
        layer_data += struct.pack("<H", 0)        # type (normal)
        layer_data += struct.pack("<H", 0)        # child level
        layer_data += struct.pack("<H", 0)        # default width (ignored)
        layer_data += struct.pack("<H", 0)        # default height (ignored)
        layer_data += struct.pack("<H", 0)        # blend mode (normal)
        layer_data += struct.pack("<B", 255)      # opacity
        layer_data += bytearray(3)                # reserved
        layer_name = "Layer 1"
        layer_data += struct.pack("<H", len(layer_name))
        layer_data += layer_name.encode("utf-8")

        frame_chunks += struct.pack("<I", len(layer_data) + 6)  # chunk size
        frame_chunks += struct.pack("<H", 0x2004)                # chunk type
        frame_chunks += layer_data

        # Cel chunk (0x2005) — compressed (type 2)
        cel_data = bytearray()
        cel_data += struct.pack("<H", 0)    # layer index
        cel_data += struct.pack("<h", 0)    # x
        cel_data += struct.pack("<h", 0)    # y
        cel_data += struct.pack("<B", 255)  # opacity
        cel_data += struct.pack("<H", 2)    # cel type: compressed
        cel_data += struct.pack("<h", 0)    # z-index
        cel_data += bytearray(5)            # reserved
        cel_data += struct.pack("<H", 4)    # width
        cel_data += struct.pack("<H", 4)    # height
        # 4x4 RGBA = 64 bytes, all red
        raw_pixels = bytes([255, 0, 0, 255] * 16)
        compressed = zlib.compress(raw_pixels)
        cel_data += compressed

        frame_chunks += struct.pack("<I", len(cel_data) + 6)
        frame_chunks += struct.pack("<H", 0x2005)
        frame_chunks += cel_data

        # Frame header
        frame_header = bytearray()
        frame_size = 16 + len(frame_chunks)
        frame_header += struct.pack("<I", frame_size)
        frame_header += struct.pack("<H", 0xF1FA)  # magic
        old_chunks = min(2, 0xFFFF)
        frame_header += struct.pack("<H", old_chunks)
        frame_header += struct.pack("<H", 100)  # duration
        frame_header += bytearray(2)            # reserved
        frame_header += struct.pack("<I", 2)    # new chunk count

        file_data = bytes(header) + bytes(frame_header) + bytes(frame_chunks)
        # Fix file size
        file_data = struct.pack("<I", len(file_data)) + file_data[4:]

        with tempfile.NamedTemporaryFile(suffix=".ase", delete=False, mode="wb") as f:
            f.write(file_data)
            path = f.name
        try:
            tl, pal = load_aseprite(path)
            assert tl.width == 4
            assert tl.height == 4
            assert tl.frame_count == 1
            assert len(tl.get_frame_obj(0).layers) == 1
            # Check the pixel is red
            pixel = tl.get_frame_obj(0).layers[0].pixels.get_pixel(0, 0)
            assert pixel == (255, 0, 0, 255)
        finally:
            os.unlink(path)
```

- [ ] **Step 2: Implement**

Create `src/aseprite_import.py`:

```python
"""Aseprite (.ase/.aseprite) file import."""
from __future__ import annotations
import struct
import sys
import zlib
import numpy as np
from src.pixel_data import PixelGrid
from src.animation import AnimationTimeline, Frame
from src.layer import Layer
from src.palette import Palette


ASE_BLEND_MAP = {
    0: "normal", 1: "multiply", 2: "screen", 3: "overlay",
    4: "darken", 5: "lighten", 10: "difference",
    16: "addition", 17: "subtract",
}


def load_aseprite(path: str) -> tuple[AnimationTimeline, Palette]:
    """Parse .ase/.aseprite file and return (timeline, palette)."""
    with open(path, "rb") as f:
        data = f.read()

    pos = 0

    def read(fmt, offset=None):
        nonlocal pos
        if offset is not None:
            pos = offset
        size = struct.calcsize(fmt)
        val = struct.unpack_from(fmt, data, pos)
        pos += size
        return val if len(val) > 1 else val[0]

    # --- Header (128 bytes) ---
    _file_size = read("<I")
    magic = read("<H")
    if magic != 0xA5E0:
        raise ValueError("Not a valid Aseprite file")
    num_frames = read("<H")
    width = read("<H")
    height = read("<H")
    color_depth = read("<H")  # 8=indexed, 16=gray, 32=rgba
    _flags = read("<I")
    _speed = read("<H")
    pos = 28
    _palette_entry = read("<I")
    pos = 128  # skip rest of header

    bpp = color_depth // 8

    # Data structures
    layer_infos = []  # list of dicts: {name, flags, blend, opacity, type}
    palette_colors = []
    frames_data = []  # list of list of (layer_idx, pixels_ndarray)
    cel_cache = {}  # for linked cels: (frame, layer) -> pixel data

    for frame_idx in range(num_frames):
        frame_start = pos
        frame_size = read("<I")
        _frame_magic = read("<H")
        old_chunks = read("<H")
        duration_ms = read("<H")
        pos += 2  # reserved
        new_chunks = read("<I")
        chunk_count = new_chunks if new_chunks != 0 else old_chunks

        cels = []  # (layer_idx, pixels_ndarray) for this frame

        for _ in range(chunk_count):
            chunk_size = read("<I")
            chunk_type = read("<H")
            chunk_data_start = pos
            chunk_data_size = chunk_size - 6

            if chunk_type == 0x2004:  # Layer
                flags = struct.unpack_from("<H", data, pos)[0]
                layer_type = struct.unpack_from("<H", data, pos + 2)[0]
                _child_level = struct.unpack_from("<H", data, pos + 4)[0]
                blend_mode = struct.unpack_from("<H", data, pos + 10)[0]
                opacity = struct.unpack_from("<B", data, pos + 12)[0]
                name_pos = pos + 16
                name_len = struct.unpack_from("<H", data, name_pos)[0]
                name = data[name_pos + 2:name_pos + 2 + name_len].decode("utf-8", errors="replace")
                layer_infos.append({
                    "name": name,
                    "flags": flags,
                    "blend": ASE_BLEND_MAP.get(blend_mode, "normal"),
                    "opacity": opacity / 255.0,
                    "visible": bool(flags & 1),
                    "type": layer_type,
                })

            elif chunk_type == 0x2005:  # Cel
                layer_index = struct.unpack_from("<H", data, pos)[0]
                x_pos = struct.unpack_from("<h", data, pos + 2)[0]
                y_pos = struct.unpack_from("<h", data, pos + 4)[0]
                cel_opacity = struct.unpack_from("<B", data, pos + 6)[0]
                cel_type = struct.unpack_from("<H", data, pos + 7)[0]
                cel_header_size = 16  # base cel header

                if cel_type == 0:  # Raw
                    cel_w = struct.unpack_from("<H", data, pos + cel_header_size)[0]
                    cel_h = struct.unpack_from("<H", data, pos + cel_header_size + 2)[0]
                    pixel_start = pos + cel_header_size + 4
                    raw = data[pixel_start:pixel_start + cel_w * cel_h * bpp]
                    pixels = _decode_pixels(raw, cel_w, cel_h, color_depth, palette_colors)
                    canvas = _place_cel(pixels, x_pos, y_pos, cel_w, cel_h, width, height)
                    cels.append((layer_index, canvas))
                    cel_cache[(frame_idx, layer_index)] = canvas

                elif cel_type == 1:  # Linked
                    linked_frame = struct.unpack_from("<H", data, pos + cel_header_size)[0]
                    cached = cel_cache.get((linked_frame, layer_index))
                    if cached is not None:
                        cels.append((layer_index, cached.copy()))

                elif cel_type == 2:  # Compressed
                    cel_w = struct.unpack_from("<H", data, pos + cel_header_size)[0]
                    cel_h = struct.unpack_from("<H", data, pos + cel_header_size + 2)[0]
                    compressed_start = pos + cel_header_size + 4
                    compressed_data = data[compressed_start:chunk_data_start + chunk_data_size]
                    raw = zlib.decompress(compressed_data)
                    pixels = _decode_pixels(raw, cel_w, cel_h, color_depth, palette_colors)
                    canvas = _place_cel(pixels, x_pos, y_pos, cel_w, cel_h, width, height)
                    cels.append((layer_index, canvas))
                    cel_cache[(frame_idx, layer_index)] = canvas

            elif chunk_type == 0x2019:  # Palette (new format)
                pal_size = struct.unpack_from("<I", data, pos)[0]
                first_idx = struct.unpack_from("<I", data, pos + 4)[0]
                last_idx = struct.unpack_from("<I", data, pos + 8)[0]
                p = pos + 20  # skip reserved
                while len(palette_colors) <= last_idx:
                    palette_colors.append((0, 0, 0, 255))
                for idx in range(first_idx, last_idx + 1):
                    entry_flags = struct.unpack_from("<H", data, p)[0]
                    r = data[p + 2]
                    g = data[p + 3]
                    b = data[p + 4]
                    a = data[p + 5]
                    palette_colors[idx] = (r, g, b, a)
                    p += 6
                    if entry_flags & 1:  # has name
                        name_len = struct.unpack_from("<H", data, p)[0]
                        p += 2 + name_len

            elif chunk_type == 0x0004:  # Old palette
                packets = struct.unpack_from("<H", data, pos)[0]
                p = pos + 2
                idx = 0
                for _ in range(packets):
                    skip = data[p]
                    count = data[p + 1]
                    if count == 0:
                        count = 256
                    p += 2
                    idx += skip
                    for _ in range(count):
                        r, g, b = data[p], data[p + 1], data[p + 2]
                        while len(palette_colors) <= idx:
                            palette_colors.append((0, 0, 0, 255))
                        palette_colors[idx] = (r, g, b, 255)
                        p += 3
                        idx += 1

            elif chunk_type == 0x2018:  # Frame tags
                pass  # handled below after frames

            pos = chunk_data_start + chunk_data_size

        frames_data.append((cels, duration_ms))
        pos = frame_start + frame_size

    # --- Build timeline ---
    timeline = AnimationTimeline(width, height)
    timeline._frames.clear()

    # Filter to normal layers only (skip group/tilemap)
    normal_layer_indices = [i for i, info in enumerate(layer_infos)
                           if info["type"] == 0]

    if not normal_layer_indices:
        normal_layer_indices = [0]
        layer_infos = [{"name": "Layer 1", "flags": 1, "blend": "normal",
                        "opacity": 1.0, "visible": True, "type": 0}]

    for frame_idx, (cels, duration_ms) in enumerate(frames_data):
        frame = Frame(width, height, name=f"Frame {frame_idx + 1}")
        frame.layers.clear()
        frame.duration_ms = duration_ms

        cel_map = {layer_idx: pixels for layer_idx, pixels in cels}

        for li in normal_layer_indices:
            info = layer_infos[li] if li < len(layer_infos) else {
                "name": f"Layer {li}", "blend": "normal", "opacity": 1.0, "visible": True}
            layer = Layer(info["name"], width, height)
            layer.blend_mode = info["blend"]
            layer.opacity = info["opacity"]
            layer.visible = info["visible"]

            if li in cel_map:
                layer.pixels._pixels = cel_map[li]

            frame.layers.append(layer)

        if not frame.layers:
            frame.layers.append(Layer("Layer 1", width, height))
        frame.active_layer_index = 0
        timeline._frames.append(frame)

    # Build palette
    palette = Palette("Imported")
    if palette_colors:
        palette.colors = list(palette_colors)
    palette.selected_index = 0

    # Parse frame tags (re-read file for tags)
    timeline.tags = _parse_tags(data)

    return timeline, palette


def _decode_pixels(raw: bytes, w: int, h: int, depth: int,
                   palette: list) -> np.ndarray:
    """Decode raw pixel bytes to RGBA ndarray."""
    if depth == 32:  # RGBA
        arr = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 4).copy()
    elif depth == 16:  # Grayscale
        arr = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 2)
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[:, :, 0] = arr[:, :, 0]
        rgba[:, :, 1] = arr[:, :, 0]
        rgba[:, :, 2] = arr[:, :, 0]
        rgba[:, :, 3] = arr[:, :, 1]
        arr = rgba
    elif depth == 8:  # Indexed
        indices = np.frombuffer(raw, dtype=np.uint8).reshape(h, w)
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        for i, color in enumerate(palette):
            mask = indices == i
            rgba[mask] = color
        arr = rgba
    else:
        arr = np.zeros((h, w, 4), dtype=np.uint8)
    return arr


def _place_cel(pixels: np.ndarray, x: int, y: int, cel_w: int, cel_h: int,
               canvas_w: int, canvas_h: int) -> np.ndarray:
    """Place cel pixel data at offset on full-size canvas."""
    canvas = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)
    # Clip to canvas bounds
    src_x0 = max(0, -x)
    src_y0 = max(0, -y)
    dst_x0 = max(0, x)
    dst_y0 = max(0, y)
    copy_w = min(cel_w - src_x0, canvas_w - dst_x0)
    copy_h = min(cel_h - src_y0, canvas_h - dst_y0)
    if copy_w > 0 and copy_h > 0:
        canvas[dst_y0:dst_y0 + copy_h, dst_x0:dst_x0 + copy_w] = \
            pixels[src_y0:src_y0 + copy_h, src_x0:src_x0 + copy_w]
    return canvas


def _parse_tags(data: bytes) -> list[dict]:
    """Find and parse frame tag chunks from raw file data."""
    tags = []
    pos = 128  # skip header
    file_size = len(data)
    while pos < file_size - 16:
        try:
            frame_size = struct.unpack_from("<I", data, pos)[0]
            magic = struct.unpack_from("<H", data, pos + 4)[0]
            if magic != 0xF1FA:
                break
            old_chunks = struct.unpack_from("<H", data, pos + 6)[0]
            new_chunks = struct.unpack_from("<I", data, pos + 12)[0]
            chunk_count = new_chunks if new_chunks != 0 else old_chunks
            cp = pos + 16
            for _ in range(chunk_count):
                if cp + 6 > file_size:
                    break
                chunk_size = struct.unpack_from("<I", data, cp)[0]
                chunk_type = struct.unpack_from("<H", data, cp + 4)[0]
                if chunk_type == 0x2018:  # Tags
                    tp = cp + 6
                    num_tags = struct.unpack_from("<H", data, tp)[0]
                    tp += 10  # skip reserved
                    for _ in range(num_tags):
                        from_frame = struct.unpack_from("<H", data, tp)[0]
                        to_frame = struct.unpack_from("<H", data, tp + 2)[0]
                        _loop_dir = struct.unpack_from("<B", data, tp + 4)[0]
                        _repeat = struct.unpack_from("<H", data, tp + 5)[0]
                        tp += 17  # skip to name
                        name_len = struct.unpack_from("<H", data, tp)[0]
                        name = data[tp + 2:tp + 2 + name_len].decode("utf-8", errors="replace")
                        tp += 2 + name_len
                        tags.append({"name": name, "start": from_frame, "end": to_frame})
                cp += chunk_size
            pos += frame_size
        except (struct.error, IndexError):
            break
    return tags
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_interop_color.py::TestAsepriteImport -v --tb=short`
Expected: ALL PASS

---

### Task 10: CLI + Scripting API integration

**Files:**
- Modify: `src/cli.py`
- Modify: `src/scripting.py`
- Test: `tests/test_interop_color.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_interop_color.py`:

```python
class TestCLIIntegration:
    def test_cli_export_frames_format(self):
        """Test that --format frames produces numbered PNGs."""
        tl = AnimationTimeline(4, 4)
        tl.add_frame()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Save a .retro file
            from src.project import save_project
            retro_path = os.path.join(tmpdir, "test.retro")
            save_project(retro_path, tl, Palette("Pico-8"))

            out_path = os.path.join(tmpdir, "out.png")
            from src.cli import cmd_export
            # cmd_export takes positional params, not an args namespace
            result = cmd_export(retro_path, out_path, format="frames",
                                scale=1, frame=0, columns=0, layer=None)
            assert result == 0
            assert os.path.exists(os.path.join(tmpdir, "out_000.png"))
            assert os.path.exists(os.path.join(tmpdir, "out_001.png"))

    def test_cli_export_ase_input(self):
        """Test that .ase input files are detected and loaded."""
        # This test requires a valid .ase file — covered by TestAsepriteImport
        pass


class TestIndexedSafetyFixes:
    """Tests for indexed-mode safety in existing code paths."""

    def setup_method(self):
        self.palette = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]

    def test_palette_remove_color(self):
        from src.palette import Palette
        pal = Palette("Test")
        pal.colors = list(self.palette)
        pal.selected_index = 2
        pal.remove_color(2)
        assert len(pal.colors) == 2
        assert pal.selected_index == 1  # adjusted

    def test_palette_replace_color(self):
        from src.palette import Palette
        pal = Palette("Test")
        pal.colors = list(self.palette)
        pal.replace_color(0, (128, 128, 128, 255))
        assert pal.colors[0] == (128, 128, 128, 255)

    def test_merge_down_indexed_layers(self):
        """merge_down should not crash on indexed layers."""
        frame = Frame(4, 4, color_mode="indexed", palette=self.palette)
        frame.layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))
        layer2 = frame.add_layer("Top")
        layer2.pixels.set_pixel(1, 0, (0, 255, 0, 255))
        frame.merge_down(1)
        assert len(frame.layers) == 1
        # Red pixel from bottom layer preserved
        assert frame.layers[0].pixels.get_pixel(0, 0) == (255, 0, 0, 255)

    def test_apply_filter_indexed_layer(self):
        """apply_filter should work on indexed layers without crashing."""
        tl = AnimationTimeline(4, 4)
        tl.color_mode = "indexed"
        tl.palette_ref = self.palette
        frame = tl.get_frame_obj(0)
        frame.layers[0] = Layer("L1", 4, 4, color_mode="indexed", palette=self.palette)
        frame.layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))

        api = RetroSpriteAPI(timeline=tl, palette=Palette("Test"), app=None)
        api.palette.colors = list(self.palette)

        # Identity filter — should not crash
        def identity(pg):
            return pg
        api.apply_filter(identity)
        assert frame.layers[0].pixels.get_pixel(0, 0) == (255, 0, 0, 255)

    def test_layer_from_grid_indexed(self):
        """Layer.from_grid should detect IndexedPixelGrid."""
        grid = IndexedPixelGrid(4, 4, self.palette)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        layer = Layer.from_grid("test", grid)
        assert layer.color_mode == "indexed"
        assert isinstance(layer.pixels, IndexedPixelGrid)
        assert layer.pixels.get_pixel(0, 0) == (255, 0, 0, 255)


class TestCLIExportFrames:
    def test_api_export_frames(self):
        tl = AnimationTimeline(4, 4)
        palette = Palette("Pico-8")
        api = RetroSpriteAPI(timeline=tl, palette=palette, app=None)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "sprite.png")
            paths = api.export_frames(out)
            assert len(paths) == 1
            assert os.path.exists(paths[0])
```

- [ ] **Step 2: Implement CLI frames format**

In `src/cli.py`, in `cmd_export` (which takes positional params: `input_path, output_path, format, scale, frame, columns, layer`):

The existing `"frames"` format case already exists (lines 103-110) and uses `export_png` per-frame. Replace it to use `export_png_sequence`:

```python
        elif fmt == "frames":
            from src.export import export_png_sequence
            export_png_sequence(api.timeline, output_path, scale=scale,
                                layer=_parse_layer(layer))
```

Also add `.ase`/`.aseprite` input file support — replace the `load_project(input_path)` call at the top of `cmd_export`:
```python
    ext = os.path.splitext(input_path)[1].lower()
    if ext in ('.ase', '.aseprite'):
        from src.aseprite_import import load_aseprite
        timeline, palette = load_aseprite(input_path)
    else:
        timeline, palette = load_project(input_path)
    api = RetroSpriteAPI(timeline=timeline, palette=palette, app=None)
```

In `src/scripting.py`, add `export_frames` method:
```python
    def export_frames(self, path: str, scale: int = 1, layer=None) -> list[str]:
        """Export each frame as a numbered PNG."""
        from src.export import export_png_sequence
        return export_png_sequence(self.timeline, path, scale, layer)
```

- [ ] **Step 2b: Fix scripting.py apply_filter for indexed layers**

In `src/scripting.py`, `apply_filter` (line 131-161) accesses `._pixels` directly which crashes on `IndexedPixelGrid`. Wrap with indexed-awareness:

Replace the selection branch (lines 146-158):
```python
        if selection:
            import numpy as np
            pixels = target_layer.pixels
            xs = [p[0] for p in selection]
            ys = [p[1] for p in selection]
            x0, x1 = min(xs), max(xs) + 1
            y0, y1 = min(ys), max(ys) + 1
            # Resolve to PixelGrid for filter
            if hasattr(pixels, '_indices'):
                full_pg = pixels.to_pixelgrid()
            else:
                full_pg = pixels
            sub = PixelGrid(x1 - x0, y1 - y0)
            sub._pixels = full_pg._pixels[y0:y1, x0:x1].copy()
            result_sub = func(sub)
            for sx, sy in selection:
                lx, ly = sx - x0, sy - y0
                if 0 <= lx < result_sub.width and 0 <= ly < result_sub.height:
                    color = tuple(int(v) for v in result_sub._pixels[ly, lx])
                    pixels.set_pixel(sx, sy, color)
```

Replace the else branch (lines 159-161):
```python
        else:
            if hasattr(target_layer.pixels, '_indices'):
                # Convert indexed→PixelGrid, apply filter, convert back
                pg = target_layer.pixels.to_pixelgrid()
                result = func(pg)
                # Write back pixel-by-pixel to respect palette snapping
                for y in range(result.height):
                    for x in range(result.width):
                        color = result.get_pixel(x, y)
                        if color:
                            target_layer.pixels.set_pixel(x, y, color)
            else:
                result = func(target_layer.pixels)
                target_layer.pixels._pixels = result._pixels.copy()
```

- [ ] **Step 2c: Fix merge_down for indexed layers**

In `src/animation.py`, `Frame.merge_down` (line 79) does `below.pixels._pixels = merged._pixels.copy()` which crashes if `below` is indexed. Add an indexed guard:

```python
            # After flatten_layers produces merged PixelGrid:
            if hasattr(below, 'is_tilemap') and below.is_tilemap():
                # ... existing tilemap code ...
            elif below.color_mode == "indexed":
                # Flatten produces PixelGrid; write back to indexed grid
                for y in range(self.height):
                    for x in range(self.width):
                        color = merged.get_pixel(x, y)
                        if color:
                            below.pixels.set_pixel(x, y, color)
            else:
                below.pixels._pixels = merged._pixels.copy()
```

Also add the same guard for `above_layer` resolution — if above is indexed, resolve to PixelGrid before flatten:
```python
            if hasattr(above, 'is_tilemap') and above.is_tilemap():
                # ... existing tilemap rasterize ...
            elif above.color_mode == "indexed":
                above_layer = Layer(above.name, self.width, self.height)
                above_layer.pixels._pixels = above.pixels.to_rgba()
                above_layer.visible = above.visible
                above_layer.opacity = above.opacity
                above_layer.blend_mode = above.blend_mode
            else:
                above_layer = above
```

Same pattern for `below_layer` if below is indexed.

Apply the **exact same fix** to `AnimationTimeline.merge_down_in_all` (line 267-303), which has the identical pattern. The existing `else` at line 300 (`below.pixels._pixels = merged._pixels.copy()`) needs the same indexed guard:
```python
                if hasattr(below, 'is_tilemap') and below.is_tilemap():
                    # ... existing tilemap code ...
                elif getattr(below, 'color_mode', 'rgba') == "indexed":
                    for y in range(self.height):
                        for x in range(self.width):
                            color = merged.get_pixel(x, y)
                            if color:
                                below.pixels.set_pixel(x, y, color)
                else:
                    below.pixels._pixels = merged._pixels.copy()
```

And the above/below layer resolution blocks (lines 274-291) need indexed guards identical to `Frame.merge_down` above.

- [ ] **Step 2d: Add Palette.remove_color() and replace_color()**

In `src/palette.py`, add these methods to the `Palette` class:

```python
    def remove_color(self, index: int) -> None:
        """Remove color at index."""
        if 0 <= index < len(self.colors):
            self.colors.pop(index)
            if self.selected_index >= len(self.colors):
                self.selected_index = max(0, len(self.colors) - 1)

    def replace_color(self, index: int, color: tuple[int, int, int, int]) -> None:
        """Replace color at index."""
        if 0 <= index < len(self.colors):
            self.colors[index] = color
```

Update `cmd_info` to show actual version instead of hardcoded `(v3)`:
```python
    # Read version from file
    import json
    with open(args.input) as f:
        project_data = json.load(f)
    version = project_data.get("version", 1)
    color_mode = project_data.get("color_mode", "rgba")
    print(f"Project: {basename} (v{version})")
    # ... rest of info output
    if color_mode == "indexed":
        print(f"Color mode: indexed")
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_interop_color.py -v --tb=short`
Expected: ALL PASS

---

## Chunk 4: GUI Integration (Tasks 11-13)

### Task 11: Palette import/export UI in app.py

**Files:**
- Modify: `src/app.py`

- [ ] **Step 1: Add palette import/export to Edit or Palette menu**

In `app.py`, add menu items for palette I/O. Find where palette-related menus are built and add:

```python
        # In the Edit menu or a new Palette menu:
        palette_menu.add_command(label="Import Palette...", command=self._import_palette)
        palette_menu.add_command(label="Export Palette...", command=self._export_palette)
```

Implement the handlers:
```python
    def _import_palette(self):
        from src.ui.dialogs import ask_open_file
        path = ask_open_file(self.root, filetypes=[
            ("All Palettes", "*.gpl;*.pal;*.hex;*.ase"),
            ("GIMP Palette", "*.gpl"), ("JASC PAL", "*.pal"),
            ("HEX", "*.hex"), ("Adobe ASE", "*.ase"),
        ])
        if not path:
            return
        from src.palette_io import load_palette
        try:
            colors = load_palette(path)
        except Exception as e:
            from src.ui.dialogs import show_error
            show_error(self.root, "Import Error", str(e))
            return
        # Replace palette
        self.palette.colors.clear()
        self.palette.colors.extend(colors)
        self.palette.selected_index = 0
        self.right_panel.palette_panel.palette = self.palette
        self.right_panel.palette_panel.refresh()
        # Update indexed layer palette refs if needed
        if self.timeline.color_mode == "indexed":
            self.timeline.palette_ref = self.palette.colors
            self._update_indexed_palette_refs()
        self._update_status(f"Imported palette: {os.path.basename(path)}")

    def _export_palette(self):
        from src.ui.dialogs import ask_save_file
        path = ask_save_file(self.root, filetypes=[
            ("GIMP Palette", "*.gpl"), ("JASC PAL", "*.pal"),
            ("HEX", "*.hex"), ("Adobe ASE", "*.ase"),
        ])
        if not path:
            return
        from src.palette_io import save_palette
        try:
            save_palette(path, self.palette.colors, name=self.palette.name)
        except Exception as e:
            from src.ui.dialogs import show_error
            show_error(self.root, "Export Error", str(e))
            return
        self._update_status(f"Exported palette: {os.path.basename(path)}")

    def _update_indexed_palette_refs(self):
        """Update _palette ref on all IndexedPixelGrid layers."""
        for i in range(self.timeline.frame_count):
            frame = self.timeline.get_frame_obj(i)
            for layer in frame.layers:
                if layer.color_mode == "indexed" and hasattr(layer.pixels, '_palette'):
                    layer.pixels._palette = self.palette.colors
```

- [ ] **Step 2: Test manually** (or run full suite for regressions)

Run: `python -m pytest tests/ -v --tb=short`
Expected: ALL existing tests pass

---

### Task 12: Convert to Indexed/RGBA menu items

**Files:**
- Modify: `src/app.py`

- [ ] **Step 1: Add Image menu items**

In `app.py`, find the Image menu (or add one) and add:
```python
        image_menu.add_command(label="Convert to Indexed...", command=self._convert_to_indexed)
        image_menu.add_command(label="Convert to RGBA", command=self._convert_to_rgba)
```

Implement:
```python
    def _convert_to_indexed(self):
        if self.timeline.color_mode == "indexed":
            self._update_status("Already in indexed mode")
            return
        self._push_undo()
        self.api.convert_to_indexed()
        self.timeline.palette_ref = self.palette.colors
        self._update_indexed_palette_refs()
        self.right_panel.palette_panel.refresh()
        self._refresh_all()
        self._update_status("Converted to indexed color mode")

    def _convert_to_rgba(self):
        if self.timeline.color_mode == "rgba":
            self._update_status("Already in RGBA mode")
            return
        self._push_undo()
        self.api.convert_to_rgba()
        self._refresh_all()
        self._update_status("Converted to RGBA color mode")
```

- [ ] **Step 2: Add .ase to Open dialog**

In `_open_project`, update the filetypes to include `.ase`/`.aseprite`:
```python
        path = ask_open_file(
            self.root,
            filetypes=[("RetroSprite Projects", "*.retro"),
                       ("Aseprite Files", "*.ase;*.aseprite"),
                       ("All files", "*.*")]
        )
```

Add Aseprite detection:
```python
        ext = os.path.splitext(path)[1].lower()
        if ext in ('.ase', '.aseprite'):
            from src.aseprite_import import load_aseprite
            try:
                self.timeline, self.palette = load_aseprite(path)
            except Exception as e:
                show_error(self.root, "Import Error", str(e))
                return
        else:
            try:
                self.timeline, self.palette = load_project(path)
            except Exception as e:
                show_error(self.root, "Open Error", str(e))
                return
```

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

---

### Task 13: Full test suite verification

**Files:**
- All

- [ ] **Step 1: Run complete test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests pass (344 existing + ~50 new = ~394+)

- [ ] **Step 2: Verify no regressions in existing tests**

Check that pre-existing test counts haven't decreased. The 1 pre-existing Tkinter error in test_options_bar is expected.

- [ ] **Step 3: Quick smoke test**

Run: `python -c "from src.pixel_data import IndexedPixelGrid, nearest_palette_index; from src.palette_io import load_palette, save_palette; from src.quantize import median_cut; from src.aseprite_import import load_aseprite; from src.export import export_png_sequence; print('All imports OK')"`
Expected: "All imports OK"
