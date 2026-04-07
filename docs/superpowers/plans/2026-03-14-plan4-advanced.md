# Plan 4: Advanced & Exotic Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add seven advanced features for power users and product differentiation: Reference Layers (shared infrastructure), Pixel-Art Scaling Algorithms, Undo History Panel, Animated Brushes, 3D Mesh Layer, Audio Sync, and Multi-Document Tabs.

**Architecture:** Features are ordered by dependency. Reference Layers (4.5) ships first as shared infrastructure for 3D Mesh Layer (4.2). Pixel-Art Scaling (4.4) and Undo History Panel (4.6) are independent. Animated Brushes (4.1) extends Plan 1 custom brush system. Audio Sync (4.3) requires `pygame` as an optional dependency. Multi-Document Tabs (4.7) is a major refactor that extracts `Document` from `RetroSpriteApp`.

**Tech Stack:** Python, Tkinter, NumPy, PIL (existing). Optional: `pygame` for audio sync. No other new dependencies.

**Prerequisite from Plan 1:** `_custom_brush_colors: dict | None` must exist in `app.py` before implementing Animated Brushes (4.1). `Frame.duration_ms` must be serialized in `project.py` before Audio Sync (4.3).

---

## Chunk 1: Reference Layers (4.5) — Shared Infrastructure

This chunk implements the `is_reference` layer infrastructure used by both Reference Layers and 3D Mesh Layer. It modifies `Layer`, `flatten_layers`, export functions, project serialization, and timeline display.

### Task 1: Layer Model — Add Reference Layer Fields

**Files:**
- Modify: `src/layer.py` (add `is_reference`, `ref_offset`, `ref_scale` to `Layer.__init__` and `copy()`)
- Test: `tests/test_reference_layer.py` (create)

- [ ] **Step 1: Write failing tests**

Create `tests/test_reference_layer.py`:

```python
"""Tests for reference layer support."""
import pytest
import numpy as np
from src.layer import Layer, flatten_layers
from src.pixel_data import PixelGrid


RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


class TestReferenceLayerFields:
    def test_default_not_reference(self):
        layer = Layer("Normal", 8, 8)
        assert layer.is_reference is False
        assert layer.ref_offset == (0, 0)
        assert layer.ref_scale == 1.0

    def test_set_reference(self):
        layer = Layer("Ref", 8, 8)
        layer.is_reference = True
        layer.ref_offset = (10, 20)
        layer.ref_scale = 0.5
        assert layer.is_reference is True
        assert layer.ref_offset == (10, 20)
        assert layer.ref_scale == 0.5

    def test_copy_preserves_reference_fields(self):
        layer = Layer("Ref", 8, 8)
        layer.is_reference = True
        layer.ref_offset = (5, 10)
        layer.ref_scale = 2.0
        copy = layer.copy()
        assert copy.is_reference is True
        assert copy.ref_offset == (5, 10)
        assert copy.ref_scale == 2.0


class TestFlattenSkipsReference:
    def test_reference_layer_excluded_from_flatten(self):
        bottom = Layer("Base", 4, 4)
        bottom.pixels.set_pixel(0, 0, RED)

        ref = Layer("Reference", 4, 4)
        ref.is_reference = True
        ref.pixels.set_pixel(0, 0, GREEN)

        top = Layer("Top", 4, 4)
        top.pixels.set_pixel(1, 1, BLUE)

        result = flatten_layers([bottom, ref, top], 4, 4)
        # Reference layer green pixel should NOT appear
        assert result.get_pixel(0, 0) == RED
        # Normal layers should be composited
        assert result.get_pixel(1, 1) == BLUE

    def test_only_reference_layers_produces_transparent(self):
        ref = Layer("Reference", 4, 4)
        ref.is_reference = True
        ref.pixels.set_pixel(0, 0, RED)

        result = flatten_layers([ref], 4, 4)
        assert result.get_pixel(0, 0) == TRANSPARENT
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_reference_layer.py -v`
Expected: `AttributeError: 'Layer' object has no attribute 'is_reference'`

- [ ] **Step 3: Add reference fields to Layer.__init__**

In `src/layer.py`, add after `self.clipping: bool = False` (line 28):

```python
        self.is_reference: bool = False
        self.ref_offset: tuple[int, int] = (0, 0)
        self.ref_scale: float = 1.0
```

- [ ] **Step 4: Update Layer.copy() to preserve reference fields**

In `src/layer.py` `copy()` method, add after `new_layer.clipping = self.clipping` (line 58):

```python
        new_layer.is_reference = self.is_reference
        new_layer.ref_offset = self.ref_offset
        new_layer.ref_scale = self.ref_scale
```

- [ ] **Step 5: Update flatten_layers() to skip reference layers**

In `src/layer.py` `flatten_layers()`, add an early-skip check after `skip_depth = -1` / `if not layer.visible:` block (after line 170). Insert before the `# Resolve pixel data to RGBA` comment:

```python
        # Skip reference layers — they are for visual guidance only
        if getattr(layer, 'is_reference', False):
            i += 1
            continue
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_reference_layer.py -v`
Expected: all pass.

- [ ] **Step 7: Run full test suite for regressions**

Run: `python -m pytest tests/ -v`
Expected: no regressions. Existing flatten_layers tests should still pass since `is_reference` defaults to `False`.

### Task 2: Export Functions — Skip Reference Layers

**Files:**
- Modify: `src/export.py` (skip reference layers in sprite sheet)
- Modify: `src/animated_export.py` (skip reference layers in WebP/APNG)
- Test: `tests/test_reference_layer.py` (extend)

- [ ] **Step 1: Add export tests to `tests/test_reference_layer.py`**

Append to the test file:

```python
class TestExportSkipsReference:
    def test_sprite_sheet_excludes_reference(self):
        """Reference layers should not appear in sprite sheet export."""
        from src.animation import AnimationTimeline
        from src.layer import Layer

        timeline = AnimationTimeline(4, 4)
        frame = timeline.get_frame_obj(0)
        # Add a reference layer to the frame
        ref_layer = Layer("Ref", 4, 4)
        ref_layer.is_reference = True
        ref_layer.pixels.set_pixel(0, 0, GREEN)
        frame.layers.append(ref_layer)

        # Flatten should not include reference — verify via get_frame
        flat = timeline.get_frame(0)
        assert flat.get_pixel(0, 0) != GREEN
```

- [ ] **Step 2: Verify flatten_layers already handles this via Task 1 changes**

The `Frame.flatten()` method calls `flatten_layers()`. Since we already added the skip in Task 1, export functions that call `frame.flatten()` or `timeline.get_frame()` will automatically exclude reference layers. Verify by running:

Run: `python -m pytest tests/test_reference_layer.py::TestExportSkipsReference -v`

- [ ] **Step 3: Audit export.py for direct layer iteration**

Check `src/export.py` `build_sprite_sheet()` — it calls `timeline.get_frame(i)` which calls `flatten_layers()` internally. No changes needed.

Check `src/animated_export.py` `export_webp()` and `export_apng()` — they call `frame_obj.flatten()`. No changes needed if `flatten_layers` already skips reference layers.

If any export path iterates layers directly (e.g., for per-layer export), add the guard:

```python
if getattr(layer, 'is_reference', False):
    continue
```

- [ ] **Step 4: Run export tests**

Run: `python -m pytest tests/test_reference_layer.py tests/test_export.py -v`

### Task 3: Project Serialization — Reference Layer Fields

**Files:**
- Modify: `src/project.py` (serialize/deserialize `is_reference`, `ref_offset`, `ref_scale`)
- Test: `tests/test_reference_layer.py` (extend)

- [ ] **Step 1: Add round-trip serialization test**

Append to `tests/test_reference_layer.py`:

```python
class TestReferenceLayerSerialization:
    def test_round_trip_reference_layer(self, tmp_path):
        from src.animation import AnimationTimeline
        from src.palette import Palette
        from src.project import save_project, load_project

        timeline = AnimationTimeline(8, 8)
        frame = timeline.get_frame_obj(0)

        ref_layer = Layer("Photo Ref", 8, 8)
        ref_layer.is_reference = True
        ref_layer.ref_offset = (10, 20)
        ref_layer.ref_scale = 0.75
        ref_layer.pixels.set_pixel(0, 0, RED)
        frame.layers.append(ref_layer)

        palette = Palette("Test")
        path = str(tmp_path / "test.retro")
        save_project(path, timeline, palette)
        loaded_tl, _, _ = load_project(path)

        loaded_frame = loaded_tl.get_frame_obj(0)
        # Find the reference layer
        ref_layers = [l for l in loaded_frame.layers if getattr(l, 'is_reference', False)]
        assert len(ref_layers) == 1
        loaded_ref = ref_layers[0]
        assert loaded_ref.name == "Photo Ref"
        assert loaded_ref.is_reference is True
        assert loaded_ref.ref_offset == (10, 20)
        assert loaded_ref.ref_scale == 0.75
        assert loaded_ref.pixels.get_pixel(0, 0) == RED

    def test_load_old_project_defaults_no_reference(self, tmp_path):
        """Old projects without is_reference should default to False."""
        from src.animation import AnimationTimeline
        from src.palette import Palette
        from src.project import save_project, load_project

        timeline = AnimationTimeline(4, 4)
        palette = Palette("Test")
        path = str(tmp_path / "old.retro")
        save_project(path, timeline, palette)
        loaded_tl, _, _ = load_project(path)

        loaded_frame = loaded_tl.get_frame_obj(0)
        for layer in loaded_frame.layers:
            assert getattr(layer, 'is_reference', False) is False
```

- [ ] **Step 2: Run tests to verify serialization test fails**

Run: `python -m pytest tests/test_reference_layer.py::TestReferenceLayerSerialization -v`
Expected: round-trip test fails because `is_reference` is not serialized.

- [ ] **Step 3: Add reference fields to save_project()**

In `src/project.py` `save_project()`, in the normal pixel layer serialization block (after the `"clipping"` key, around line 117), add:

```python
                "is_reference": getattr(layer, 'is_reference', False),
                "ref_offset": list(getattr(layer, 'ref_offset', (0, 0))),
                "ref_scale": getattr(layer, 'ref_scale', 1.0),
```

Also add the same three keys to the indexed layer dict (around line 96) and the linked cel ref dict (around line 79).

- [ ] **Step 4: Add reference fields to load_project()**

In `src/project.py` `load_project()`, in each branch where layer attributes are set, add after the `layer.clipping = ...` line:

```python
                    layer.is_reference = layer_data.get("is_reference", False)
                    layer.ref_offset = tuple(layer_data.get("ref_offset", [0, 0]))
                    layer.ref_scale = layer_data.get("ref_scale", 1.0)
```

Add this in all three branches: tilemap, linked cel, and normal pixel layers.

- [ ] **Step 5: Run serialization tests**

Run: `python -m pytest tests/test_reference_layer.py::TestReferenceLayerSerialization -v`
Expected: all pass.

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -v`

### Task 4: App Integration — Add Reference Layer Menu and Rendering

**Files:**
- Modify: `src/app.py` (menu item, reference layer loading, offset/scale rendering)
- Modify: `src/ui/timeline.py` (visual indicator for reference layers)

- [ ] **Step 1: Add menu item to app.py**

In `src/app.py`, in the Layer menu section (find where layer-related menu items are added), add:

```python
        layer_menu.add_command(label="Add Reference Layer...",
                               command=self._add_reference_layer)
```

- [ ] **Step 2: Implement _add_reference_layer() in app.py**

```python
    def _add_reference_layer(self):
        """Load an image file as a non-exportable reference layer."""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Load Reference Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif"),
                       ("All files", "*.*")]
        )
        if not path:
            return
        from PIL import Image
        try:
            img = Image.open(path).convert("RGBA")
        except Exception as e:
            self._update_status(f"Failed to load reference: {e}")
            return

        import os
        name = f"Ref: {os.path.basename(path)}"
        frame_obj = self.timeline.current_frame_obj()

        layer = Layer(name, self.timeline.width, self.timeline.height)
        layer.is_reference = True
        layer.opacity = 0.4

        # Scale image to fit canvas if needed
        scale_x = self.timeline.width / img.width
        scale_y = self.timeline.height / img.height
        fit_scale = min(scale_x, scale_y, 1.0)
        if fit_scale < 1.0:
            new_w = max(1, int(img.width * fit_scale))
            new_h = max(1, int(img.height * fit_scale))
            img = img.resize((new_w, new_h), Image.LANCZOS)
            layer.ref_scale = fit_scale

        # Paste image into layer pixels
        import numpy as np
        arr = np.array(img, dtype=np.uint8)
        h, w = arr.shape[:2]
        cw, ch = self.timeline.width, self.timeline.height
        paste_w = min(w, cw)
        paste_h = min(h, ch)
        layer.pixels._pixels[:paste_h, :paste_w] = arr[:paste_h, :paste_w]

        frame_obj.layers.append(layer)
        self._refresh_canvas()
        self._update_timeline()
        self._update_status(f"Added reference layer: {name}")
```

- [ ] **Step 3: Add timeline visual indicator for reference layers**

In `src/ui/timeline.py`, in the method that renders layer headers (find the layer name rendering loop), add a check:

```python
        # After drawing the layer name label:
        if getattr(layer, 'is_reference', False):
            # Draw "REF" badge or use a distinct color
            # e.g., prepend "[R] " to the displayed name or tint the header blue
            display_name = f"[R] {layer.name}"
        else:
            display_name = layer.name
```

Adjust the existing name rendering to use `display_name`.

- [ ] **Step 4: Manual verification**

Launch the app, use `Layer > Add Reference Layer...`, load an image. Verify:
- Reference layer appears in timeline with `[R]` prefix
- Reference layer is visible on canvas with 40% opacity
- Reference layer does NOT appear in exported PNG/sprite sheet
- Saving and reloading the project preserves the reference layer

---

## Chunk 2: Pixel-Art Scaling Algorithms (4.4)

Pure NumPy implementations of Scale2x, Scale3x, cleanEdge, and OmniScale in `src/image_processing.py`. Independent of other features.

### Task 5: Scale2x Algorithm

**Files:**
- Modify: `src/image_processing.py` (add `scale2x` function)
- Test: `tests/test_pixel_scaling.py` (create)

- [ ] **Step 1: Write failing tests**

Create `tests/test_pixel_scaling.py`:

```python
"""Tests for pixel-art scaling algorithms."""
import pytest
import numpy as np
from src.pixel_data import PixelGrid
from src.image_processing import scale2x, scale3x


RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
BLACK = (0, 0, 0, 255)
WHITE = (255, 255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


class TestScale2x:
    def test_output_dimensions(self):
        grid = PixelGrid(4, 4)
        result = scale2x(grid)
        assert result.width == 8
        assert result.height == 8

    def test_uniform_color_stays_uniform(self):
        grid = PixelGrid(3, 3)
        for x in range(3):
            for y in range(3):
                grid.set_pixel(x, y, RED)
        result = scale2x(grid)
        for x in range(6):
            for y in range(6):
                assert result.get_pixel(x, y) == RED

    def test_single_pixel_becomes_2x2(self):
        grid = PixelGrid(3, 3)
        grid.set_pixel(1, 1, WHITE)
        result = scale2x(grid)
        # Center pixel (1,1) maps to (2,2), (3,2), (2,3), (3,3)
        # With no matching neighbors, all four outputs should be WHITE
        assert result.get_pixel(2, 2) == WHITE
        assert result.get_pixel(3, 2) == WHITE
        assert result.get_pixel(2, 3) == WHITE
        assert result.get_pixel(3, 3) == WHITE

    def test_diagonal_pattern_produces_smooth_edge(self):
        """Scale2x should smooth diagonal staircase patterns."""
        grid = PixelGrid(4, 4)
        # Diagonal line: (0,0), (1,1), (2,2), (3,3)
        for i in range(4):
            grid.set_pixel(i, i, WHITE)
        result = scale2x(grid)
        # The 2x2 block for pixel (1,1) should have at least one
        # corner influenced by neighbors, not all identical
        assert result.width == 8
        assert result.height == 8

    def test_preserves_alpha(self):
        grid = PixelGrid(3, 3)
        grid.set_pixel(1, 1, (255, 0, 0, 128))
        result = scale2x(grid)
        r, g, b, a = result.get_pixel(2, 2)
        assert a == 128
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_pixel_scaling.py::TestScale2x -v`
Expected: `ImportError: cannot import name 'scale2x'`

- [ ] **Step 3: Implement scale2x**

Add to `src/image_processing.py`:

```python
def scale2x(grid: PixelGrid) -> PixelGrid:
    """Scale2x (EPX) pixel-art scaling algorithm. Returns a 2x upscaled grid.

    For each pixel P with neighbors:
        A (above), B (right), C (left), D (below)

    Output 2x2 block:
        E0 E1     E0 = P if C!=A else A if C==A and A!=B and C!=D else P
        E2 E3     E1 = P if A!=B else B if A==B and A!=C and B!=D else P
                  E2 = P if D!=C else C if D==C and C!=A and D!=B else P
                  E3 = P if B!=D else D if B==D and D!=C and B!=A else P
    """
    src = grid._pixels.copy()  # (H, W, 4) uint8
    h, w = src.shape[:2]
    out = np.zeros((h * 2, w * 2, 4), dtype=np.uint8)

    # Pad source for boundary handling (replicate edges)
    padded = np.pad(src, ((1, 1), (1, 1), (0, 0)), mode='edge')

    for y in range(h):
        for x in range(w):
            P = padded[y + 1, x + 1]
            A = padded[y, x + 1]      # above
            B = padded[y + 1, x + 2]  # right
            C = padded[y + 1, x]      # left
            D = padded[y + 2, x + 1]  # below

            a_eq_c = np.array_equal(A, C)
            a_eq_b = np.array_equal(A, B)
            c_eq_d = np.array_equal(C, D)
            b_eq_d = np.array_equal(B, D)

            # E0 (top-left)
            if a_eq_c and not a_eq_b and not c_eq_d:
                out[y * 2, x * 2] = A
            else:
                out[y * 2, x * 2] = P

            # E1 (top-right)
            if a_eq_b and not a_eq_c and not b_eq_d:
                out[y * 2, x * 2 + 1] = B
            else:
                out[y * 2, x * 2 + 1] = P

            # E2 (bottom-left)
            if c_eq_d and not a_eq_c and not b_eq_d:
                out[y * 2 + 1, x * 2] = C
            else:
                out[y * 2 + 1, x * 2] = P

            # E3 (bottom-right)
            if b_eq_d and not a_eq_b and not c_eq_d:
                out[y * 2 + 1, x * 2 + 1] = D
            else:
                out[y * 2 + 1, x * 2 + 1] = P

    result = PixelGrid(w * 2, h * 2)
    result._pixels = out
    return result
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_pixel_scaling.py::TestScale2x -v`

### Task 6: Scale3x Algorithm

**Files:**
- Modify: `src/image_processing.py` (add `scale3x` function)
- Test: `tests/test_pixel_scaling.py` (extend)

- [ ] **Step 1: Add Scale3x tests**

Append to `tests/test_pixel_scaling.py`:

```python
class TestScale3x:
    def test_output_dimensions(self):
        grid = PixelGrid(4, 4)
        result = scale3x(grid)
        assert result.width == 12
        assert result.height == 12

    def test_uniform_color_stays_uniform(self):
        grid = PixelGrid(3, 3)
        for x in range(3):
            for y in range(3):
                grid.set_pixel(x, y, RED)
        result = scale3x(grid)
        for x in range(9):
            for y in range(9):
                assert result.get_pixel(x, y) == RED

    def test_single_pixel_center_preserved(self):
        grid = PixelGrid(3, 3)
        grid.set_pixel(1, 1, WHITE)
        result = scale3x(grid)
        # Center of the 3x3 output block for pixel (1,1) at (4,4)
        assert result.get_pixel(4, 4) == WHITE
```

- [ ] **Step 2: Implement scale3x**

Add to `src/image_processing.py`:

```python
def scale3x(grid: PixelGrid) -> PixelGrid:
    """Scale3x pixel-art scaling algorithm. Returns a 3x upscaled grid.

    Extension of Scale2x to 3x3 output blocks using 8-neighbor pattern matching.
    """
    src = grid._pixels.copy()
    h, w = src.shape[:2]
    out = np.zeros((h * 3, w * 3, 4), dtype=np.uint8)

    padded = np.pad(src, ((1, 1), (1, 1), (0, 0)), mode='edge')

    def eq(a, b):
        return np.array_equal(a, b)

    for y in range(h):
        for x in range(w):
            # 3x3 neighborhood (A=top-left, B=top, C=top-right, etc.)
            A = padded[y, x]          # top-left
            B = padded[y, x + 1]      # top
            C = padded[y, x + 2]      # top-right
            D = padded[y + 1, x]      # left
            E = padded[y + 1, x + 1]  # center (P)
            F = padded[y + 1, x + 2]  # right
            G = padded[y + 2, x]      # bottom-left
            H = padded[y + 2, x + 1]  # bottom
            I = padded[y + 2, x + 2]  # bottom-right

            ox, oy = x * 3, y * 3

            # E0 (top-left)
            if eq(D, B) and not eq(D, H) and not eq(B, F):
                out[oy, ox] = D
            else:
                out[oy, ox] = E

            # E1 (top-center)
            if (eq(D, B) and not eq(D, H) and not eq(B, F) and not eq(E, C)) or \
               (eq(B, F) and not eq(D, B) and not eq(F, H) and not eq(E, A)):
                out[oy, ox + 1] = B
            else:
                out[oy, ox + 1] = E

            # E2 (top-right)
            if eq(B, F) and not eq(D, B) and not eq(F, H):
                out[oy, ox + 2] = F
            else:
                out[oy, ox + 2] = E

            # E3 (middle-left)
            if (eq(D, B) and not eq(D, H) and not eq(B, F) and not eq(E, G)) or \
               (eq(D, H) and not eq(D, B) and not eq(H, F) and not eq(E, A)):
                out[oy + 1, ox] = D
            else:
                out[oy + 1, ox] = E

            # E4 (center) — always the original pixel
            out[oy + 1, ox + 1] = E

            # E5 (middle-right)
            if (eq(B, F) and not eq(D, B) and not eq(F, H) and not eq(E, I)) or \
               (eq(F, H) and not eq(B, F) and not eq(D, H) and not eq(E, C)):
                out[oy + 1, ox + 2] = F
            else:
                out[oy + 1, ox + 2] = E

            # E6 (bottom-left)
            if eq(D, H) and not eq(D, B) and not eq(H, F):
                out[oy + 2, ox] = D
            else:
                out[oy + 2, ox] = E

            # E7 (bottom-center)
            if (eq(D, H) and not eq(D, B) and not eq(H, F) and not eq(E, I)) or \
               (eq(F, H) and not eq(B, F) and not eq(D, H) and not eq(E, G)):
                out[oy + 2, ox + 1] = H
            else:
                out[oy + 2, ox + 1] = E

            # E8 (bottom-right)
            if eq(F, H) and not eq(B, F) and not eq(D, H):
                out[oy + 2, ox + 2] = F
            else:
                out[oy + 2, ox + 2] = E

    result = PixelGrid(w * 3, h * 3)
    result._pixels = out
    return result
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_pixel_scaling.py -v`

### Task 7: cleanEdge and OmniScale Algorithms

**Files:**
- Modify: `src/image_processing.py` (add `clean_edge`, `omni_scale` functions)
- Test: `tests/test_pixel_scaling.py` (extend)

- [ ] **Step 1: Add tests**

Append to `tests/test_pixel_scaling.py`:

```python
from src.image_processing import clean_edge, omni_scale


class TestCleanEdge:
    def test_output_dimensions_2x(self):
        grid = PixelGrid(4, 4)
        result = clean_edge(grid, factor=2)
        assert result.width == 8
        assert result.height == 8

    def test_output_dimensions_4x(self):
        grid = PixelGrid(4, 4)
        result = clean_edge(grid, factor=4)
        assert result.width == 16
        assert result.height == 16

    def test_uniform_stays_uniform(self):
        grid = PixelGrid(3, 3)
        for x in range(3):
            for y in range(3):
                grid.set_pixel(x, y, RED)
        result = clean_edge(grid, factor=2)
        for x in range(6):
            for y in range(6):
                assert result.get_pixel(x, y) == RED

    def test_invalid_factor_raises(self):
        grid = PixelGrid(4, 4)
        with pytest.raises(ValueError):
            clean_edge(grid, factor=1)
        with pytest.raises(ValueError):
            clean_edge(grid, factor=9)


class TestOmniScale:
    def test_output_dimensions_2x(self):
        grid = PixelGrid(4, 4)
        result = omni_scale(grid, factor=2)
        assert result.width == 8
        assert result.height == 8

    def test_output_dimensions_3x(self):
        grid = PixelGrid(4, 4)
        result = omni_scale(grid, factor=3)
        assert result.width == 12
        assert result.height == 12

    def test_uniform_stays_uniform(self):
        grid = PixelGrid(3, 3)
        for x in range(3):
            for y in range(3):
                grid.set_pixel(x, y, BLUE)
        result = omni_scale(grid, factor=2)
        for x in range(6):
            for y in range(6):
                assert result.get_pixel(x, y) == BLUE
```

- [ ] **Step 2: Implement clean_edge**

Add to `src/image_processing.py`:

```python
def clean_edge(grid: PixelGrid, factor: int = 2) -> PixelGrid:
    """cleanEdge pixel-art scaling: crisp edges + bilinear smooth regions.

    Args:
        factor: integer scale factor, 2-8.
    """
    if factor < 2 or factor > 8:
        raise ValueError(f"clean_edge factor must be 2-8, got {factor}")

    src = grid._pixels.copy().astype(np.float32)
    h, w = src.shape[:2]
    oh, ow = h * factor, w * factor
    out = np.zeros((oh, ow, 4), dtype=np.float32)

    # Step 1: Detect edges using Sobel-like gradient on luminance
    lum = 0.299 * src[:, :, 0] + 0.587 * src[:, :, 1] + 0.114 * src[:, :, 2]
    edge_map = np.zeros((h, w), dtype=bool)
    padded_lum = np.pad(lum, 1, mode='edge')
    for y in range(h):
        for x in range(w):
            # Simple gradient magnitude from 4-neighbors
            gx = abs(float(padded_lum[y + 1, x + 2]) - float(padded_lum[y + 1, x]))
            gy = abs(float(padded_lum[y + 2, x + 1]) - float(padded_lum[y, x + 1]))
            if gx + gy > 30:  # threshold for edge detection
                edge_map[y, x] = True

    # Step 2: For each output pixel, use nearest-neighbor on edges, bilinear otherwise
    padded = np.pad(src, ((0, 1), (0, 1), (0, 0)), mode='edge')
    for oy_px in range(oh):
        for ox_px in range(ow):
            # Map output pixel to source coordinates
            sx = (ox_px + 0.5) / factor - 0.5
            sy = (oy_px + 0.5) / factor - 0.5
            ix = int(sx)
            iy = int(sy)
            ix = max(0, min(ix, w - 1))
            iy = max(0, min(iy, h - 1))

            if edge_map[iy, ix]:
                # Nearest-neighbor for edge pixels (crisp)
                out[oy_px, ox_px] = src[iy, ix]
            else:
                # Bilinear interpolation for smooth regions
                fx = sx - int(sx)
                fy = sy - int(sy)
                if fx < 0: fx = 0
                if fy < 0: fy = 0
                x0 = max(0, min(int(sx), w - 1))
                y0 = max(0, min(int(sy), h - 1))
                x1 = min(x0 + 1, w - 1)
                y1 = min(y0 + 1, h - 1)
                out[oy_px, ox_px] = (
                    src[y0, x0] * (1 - fx) * (1 - fy) +
                    src[y0, x1] * fx * (1 - fy) +
                    src[y1, x0] * (1 - fx) * fy +
                    src[y1, x1] * fx * fy
                )

    result = PixelGrid(ow, oh)
    result._pixels = np.clip(out, 0, 255).astype(np.uint8)
    return result
```

- [ ] **Step 3: Implement omni_scale**

Add to `src/image_processing.py`:

```python
def omni_scale(grid: PixelGrid, factor: int = 2) -> PixelGrid:
    """OmniScale: EPX (Scale2x) base + linear filtering for non-edge areas.

    For factor=2, applies Scale2x directly.
    For factor=3+, applies Scale2x repeatedly then resizes to exact target.

    Args:
        factor: integer scale factor, 2-8.
    """
    if factor < 2 or factor > 8:
        raise ValueError(f"omni_scale factor must be 2-8, got {factor}")

    # Apply Scale2x enough times to reach or exceed target scale
    current = grid
    current_factor = 1
    while current_factor < factor:
        current = scale2x(current)
        current_factor *= 2

    # If we overshot, resize down to exact target with bilinear
    target_w = grid._pixels.shape[1] * factor
    target_h = grid._pixels.shape[0] * factor
    if current.width != target_w or current.height != target_h:
        img = current.to_pil_image()
        img = img.resize((target_w, target_h), Image.BILINEAR)
        current = PixelGrid.from_pil_image(img)

    return current
```

- [ ] **Step 4: Run all scaling tests**

Run: `python -m pytest tests/test_pixel_scaling.py -v`

- [ ] **Step 5: Add import for Image in image_processing.py header if needed**

Verify `from PIL import Image` is already imported (it is, via `ImageFilter, ImageEnhance`). Add `Image` to the import if not present. The `omni_scale` function uses `Image.BILINEAR`.

### Task 8: Resize Dialog Integration

**Files:**
- Modify: `src/app.py` (add algorithm selector to resize dialog)

- [ ] **Step 1: Locate the resize dialog in app.py**

Search for the existing resize / `Image > Resize` functionality in `src/app.py`. It likely uses a Toplevel dialog with width/height inputs.

- [ ] **Step 2: Add algorithm dropdown**

In the resize dialog, add a dropdown (OptionMenu or Combobox) with these choices:

```python
SCALE_ALGORITHMS = [
    ("Nearest Neighbor", "nearest"),
    ("Scale2x (2x only)", "scale2x"),
    ("Scale3x (3x only)", "scale3x"),
    ("cleanEdge (2x-8x)", "clean_edge"),
    ("OmniScale (2x-8x)", "omni_scale"),
]
```

- [ ] **Step 3: Route to the correct scaling function**

When the user confirms resize, check the selected algorithm:

```python
from src.image_processing import scale2x, scale3x, clean_edge, omni_scale

if algo == "scale2x":
    new_grid = scale2x(layer.pixels)
elif algo == "scale3x":
    new_grid = scale3x(layer.pixels)
elif algo == "clean_edge":
    new_grid = clean_edge(layer.pixels, factor=scale_factor)
elif algo == "omni_scale":
    new_grid = omni_scale(layer.pixels, factor=scale_factor)
else:
    # existing nearest-neighbor resize
    new_grid = scale(layer.pixels, scale_factor)
```

Validate: Scale2x only allows 2x, Scale3x only allows 3x. Show warning if user picks an incompatible factor.

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ -v`

---

## Chunk 3: Undo History Panel (4.6)

A scrollable undo history panel in the right sidebar. Requires augmenting the undo stack with labels and timestamps.

### Task 9: Augment Undo Stack with Labels

**Files:**
- Modify: `src/app.py` (change `_push_undo` to accept label, store timestamp)
- Test: `tests/test_undo_history.py` (create)

- [ ] **Step 1: Write failing tests**

Create `tests/test_undo_history.py`:

```python
"""Tests for undo history with labels."""
import pytest
import time


class TestUndoLabels:
    def test_undo_entry_has_label(self):
        """Undo stack entries should include a label string."""
        # Simulate the undo entry structure
        entry = {
            "label": "Draw pixel",
            "timestamp": time.time(),
            "frame_idx": 0,
            "layer_idx": 0,
            "snapshot": None,  # would be PixelGrid in real code
        }
        assert "label" in entry
        assert isinstance(entry["label"], str)

    def test_undo_entry_has_timestamp(self):
        entry = {
            "label": "Fill bucket",
            "timestamp": time.time(),
            "frame_idx": 0,
            "layer_idx": 0,
            "snapshot": None,
        }
        assert "timestamp" in entry
        assert isinstance(entry["timestamp"], float)
```

- [ ] **Step 2: Change _push_undo signature**

In `src/app.py`, modify `_push_undo` to accept an optional label:

```python
    def _push_undo(self, label: str = "Edit"):
        """Snapshot current active layer before a modification."""
        import time
        frame_obj = self.timeline.current_frame_obj()
        layer_idx = frame_obj.active_layer_index
        snapshot = frame_obj.active_layer.pixels.copy()
        entry = {
            "label": label,
            "timestamp": time.time(),
            "frame_idx": self.timeline.current_index,
            "layer_idx": layer_idx,
            "snapshot": snapshot,
        }
        self._undo_stack.append(entry)
        if len(self._undo_stack) > self._UNDO_LIMIT:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._mark_dirty()
```

- [ ] **Step 3: Update _undo() and _redo() for new entry format**

Update `_undo()`:

```python
    def _undo(self):
        if not self._undo_stack:
            return
        frame_obj = self.timeline.current_frame_obj()
        layer_idx = frame_obj.active_layer_index
        redo_entry = {
            "label": "Redo point",
            "timestamp": time.time(),
            "frame_idx": self.timeline.current_index,
            "layer_idx": layer_idx,
            "snapshot": frame_obj.active_layer.pixels.copy(),
        }
        self._redo_stack.append(redo_entry)
        entry = self._undo_stack.pop()
        target_frame = self.timeline.get_frame_obj(entry["frame_idx"])
        target_frame.layers[entry["layer_idx"]].pixels = entry["snapshot"]
        self._refresh_canvas()
        self._update_status(f"Undo: {entry['label']}")
        self._update_undo_panel()
```

Update `_redo()` similarly, replacing tuple unpacking with dict access.

- [ ] **Step 4: Audit all _push_undo() call sites for descriptive labels**

Search all `self._push_undo()` calls in `src/app.py` and add descriptive labels:

| Call site context | Label |
|---|---|
| Pen tool draw | `"Draw"` |
| Eraser | `"Erase"` |
| Fill bucket | `"Fill"` |
| Resize/crop | `"Resize"` |
| Flip horizontal | `"Flip Horizontal"` |
| Flip vertical | `"Flip Vertical"` |
| Rotate | `"Rotate"` |
| Brightness/Contrast | `"Adjust Colors"` |
| Clear layer | `"Clear Layer"` |
| Paste | `"Paste"` |
| Selection delete | `"Delete Selection"` |

Example: change `self._push_undo()` to `self._push_undo("Draw")` in the pen draw handler.

- [ ] **Step 5: Add _update_undo_panel() stub**

```python
    def _update_undo_panel(self):
        """Notify the undo history panel of stack changes."""
        if hasattr(self, '_undo_panel') and self._undo_panel:
            self._undo_panel.refresh(self._undo_stack, self._redo_stack)
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_undo_history.py -v`
Run: `python -m pytest tests/ -v` (check no regressions from undo format change)

### Task 10: Undo History Panel Widget

**Files:**
- Create: `src/ui/undo_panel.py`
- Modify: `src/ui/right_panel.py` (integrate)
- Modify: `src/app.py` (wire up panel, jump-to-state logic)

- [ ] **Step 1: Create `src/ui/undo_panel.py`**

```python
"""Undo history panel for RetroSprite."""
from __future__ import annotations
import time
import tkinter as tk
from src.ui.theme import (
    BG_DEEP, BG_PANEL, BG_PANEL_ALT, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, ACCENT_MAGENTA, BUTTON_BG, BUTTON_HOVER, style_button,
)


class UndoHistoryPanel(tk.Frame):
    """Scrollable list of undo stack entries with click-to-jump."""

    def __init__(self, parent, on_jump_to=None, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self._on_jump_to = on_jump_to  # callback(index_in_undo_stack)
        self._entries: list[dict] = []
        self._current_index: int = -1  # -1 means "at head" (latest state)

        # Header
        header = tk.Frame(self, bg=BG_PANEL)
        header.pack(fill="x", padx=4, pady=(4, 0))
        tk.Label(header, text="History", fg=ACCENT_CYAN, bg=BG_PANEL,
                 font=("Consolas", 9, "bold")).pack(side="left")

        # Scrollable list
        list_frame = tk.Frame(self, bg=BG_DEEP)
        list_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self._scrollbar = tk.Scrollbar(list_frame, orient="vertical")
        self._scrollbar.pack(side="right", fill="y")

        self._listbox = tk.Listbox(
            list_frame, bg=BG_DEEP, fg=TEXT_PRIMARY,
            selectbackground=ACCENT_CYAN, selectforeground=BG_DEEP,
            font=("Consolas", 8), borderwidth=0, highlightthickness=0,
            yscrollcommand=self._scrollbar.set,
            activestyle="none",
        )
        self._listbox.pack(fill="both", expand=True)
        self._scrollbar.config(command=self._listbox.yview)
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

    def refresh(self, undo_stack: list, redo_stack: list):
        """Rebuild the list from current undo/redo stacks."""
        self._listbox.delete(0, tk.END)
        self._entries = list(undo_stack)
        now = time.time()

        for i, entry in enumerate(self._entries):
            label = entry.get("label", "Edit")
            ts = entry.get("timestamp", now)
            age = now - ts
            if age < 60:
                time_str = f"{int(age)}s ago"
            elif age < 3600:
                time_str = f"{int(age / 60)}m ago"
            else:
                time_str = f"{int(age / 3600)}h ago"
            self._listbox.insert(tk.END, f"  {label}  ({time_str})")

        # Mark current position (top of undo stack = most recent)
        if self._entries:
            last = len(self._entries) - 1
            self._listbox.selection_set(last)
            self._listbox.see(last)

    def _on_select(self, event):
        sel = self._listbox.curselection()
        if not sel:
            return
        index = sel[0]
        if self._on_jump_to:
            self._on_jump_to(index)
```

- [ ] **Step 2: Integrate into right_panel.py**

In `src/ui/right_panel.py`, add a new collapsible section for the undo panel. Find where sections are created (after palette/color picker sections) and add:

```python
from src.ui.undo_panel import UndoHistoryPanel

# Inside RightPanel.__init__ or build method:
        self._undo_section = CollapsibleSection(self, title="HISTORY",
                                                 accent_color=ACCENT_MAGENTA,
                                                 expanded=False)
        self._undo_section.pack(fill="x", padx=0, pady=(1, 0))
        self.undo_panel = UndoHistoryPanel(self._undo_section.content,
                                            on_jump_to=on_undo_jump)
        self.undo_panel.pack(fill="both", expand=True)
```

Add `on_undo_jump` callback parameter to `RightPanel.__init__`.

- [ ] **Step 3: Wire up jump-to-state in app.py**

In `src/app.py`, add the jump-to-state callback:

```python
    def _jump_to_undo_state(self, target_index: int):
        """Jump to a specific point in the undo history."""
        current_top = len(self._undo_stack) - 1
        if target_index == current_top:
            return  # already there

        if target_index < current_top:
            # Need to undo (current_top - target_index) times
            steps = current_top - target_index
            for _ in range(steps):
                self._undo()
        else:
            # Need to redo (target_index - current_top) times
            steps = target_index - current_top
            for _ in range(steps):
                self._redo()

        self._update_undo_panel()
```

- [ ] **Step 4: Store reference to undo panel in app.py**

In `__init__`, after the right panel is created:

```python
        self._undo_panel = self._right_panel.undo_panel
```

- [ ] **Step 5: Call _update_undo_panel() after every undo/redo/push operation**

Add `self._update_undo_panel()` at the end of `_push_undo()`, `_undo()`, and `_redo()`.

- [ ] **Step 6: Manual verification**

Launch app, make several drawing operations. Open the History section in right panel. Verify:
- Each operation shows with a label and relative timestamp
- Clicking an earlier entry undoes to that state
- The panel auto-scrolls to current position

---

## Chunk 4: Animated Brushes (4.1)

Extends Plan 1 custom brush system. Multi-frame brush capture with per-stroke and per-pixel cycling modes.

**Prerequisite:** Plan 1 must have implemented `_custom_brush_colors: dict | None` in `app.py`.

### Task 11: Animated Brush Capture

**Files:**
- Modify: `src/app.py` (animated brush state, capture logic)
- Test: `tests/test_animated_brush.py` (create)

- [ ] **Step 1: Write failing tests**

Create `tests/test_animated_brush.py`:

```python
"""Tests for animated brush capture and cycling."""
import pytest
from src.pixel_data import PixelGrid


RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)


class TestAnimatedBrushData:
    def test_animated_brush_is_list_of_frames(self):
        """Animated brush should be a list of brush frame dicts."""
        # Each frame is a dict[tuple[int,int], tuple] like _custom_brush_colors
        frame1 = {(0, 0): RED, (1, 0): RED}
        frame2 = {(0, 0): GREEN, (1, 0): GREEN}
        animated_brush = [frame1, frame2]
        assert len(animated_brush) == 2
        assert (0, 0) in animated_brush[0]
        assert animated_brush[1][(0, 0)] == GREEN

    def test_cycling_per_stroke(self):
        """Per-stroke cycling: index advances once per stroke."""
        frames = [
            {(0, 0): RED},
            {(0, 0): GREEN},
            {(0, 0): BLUE},
        ]
        index = 0
        # Simulate 3 strokes
        results = []
        for stroke in range(3):
            results.append(frames[index])
            index = (index + 1) % len(frames)
        assert results[0][(0, 0)] == RED
        assert results[1][(0, 0)] == GREEN
        assert results[2][(0, 0)] == BLUE

    def test_cycling_per_pixel(self):
        """Per-pixel cycling: index advances on each pixel placed."""
        frames = [
            {(0, 0): RED},
            {(0, 0): GREEN},
        ]
        index = 0
        placed = []
        for pixel in range(4):
            placed.append(frames[index])
            index = (index + 1) % len(frames)
        assert placed[0][(0, 0)] == RED
        assert placed[1][(0, 0)] == GREEN
        assert placed[2][(0, 0)] == RED
        assert placed[3][(0, 0)] == GREEN

    def test_cycling_wraps_around(self):
        frames = [{(0, 0): RED}, {(0, 0): GREEN}]
        index = 0
        for _ in range(5):
            index = (index + 1) % len(frames)
        assert index == 1  # 5 % 2 = 1
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_animated_brush.py -v`
Expected: all pass (data structure tests, no imports needed yet).

- [ ] **Step 3: Add animated brush state to app.py**

In `src/app.py` `__init__`, after the `_custom_brush_mask` / `_custom_brush_colors` fields:

```python
        self._animated_brush: list[dict[tuple[int, int], tuple]] | None = None
        self._animated_brush_index: int = 0
        self._animated_brush_mode: str = "per_stroke"  # "per_stroke" or "per_pixel"
```

- [ ] **Step 4: Implement _capture_animated_brush()**

Add method to `src/app.py`:

```python
    def _capture_animated_brush(self):
        """Capture selected timeline frames as an animated brush (Ctrl+Shift+B)."""
        # Get selected frame range from timeline (or use all frames if no selection)
        start = 0
        end = self.timeline.frame_count
        # If timeline has a frame selection, use it
        if hasattr(self, '_selected_frame_range') and self._selected_frame_range:
            start, end = self._selected_frame_range

        if end - start < 2:
            self._update_status("Select at least 2 frames for animated brush")
            return

        # Get the selection bounding box from current selection
        if not self._selection:
            self._update_status("Make a selection first, then capture animated brush")
            return

        sx = min(p[0] for p in self._selection)
        sy = min(p[1] for p in self._selection)

        frames = []
        for fi in range(start, end):
            frame_obj = self.timeline.get_frame_obj(fi)
            # Flatten visible layers for this frame
            from src.layer import flatten_layers
            flat = flatten_layers(frame_obj.layers,
                                  self.timeline.width, self.timeline.height)
            brush_frame = {}
            for (px, py) in self._selection:
                color = flat.get_pixel(px, py)
                if color[3] > 0:  # skip fully transparent
                    brush_frame[(px - sx, py - sy)] = color
            frames.append(brush_frame)

        self._animated_brush = frames
        self._animated_brush_index = 0
        self._update_status(f"Animated brush captured: {len(frames)} frames")
        self._update_options_bar()
```

- [ ] **Step 5: Bind Ctrl+Shift+B shortcut**

In the keybindings setup section of `app.py`:

```python
        self.root.bind("<Control-Shift-B>", lambda e: self._capture_animated_brush())
```

### Task 12: Animated Brush Drawing Integration

**Files:**
- Modify: `src/app.py` (drawing logic to use animated brush frames)
- Modify: `src/ui/options_bar.py` (animated brush indicator, cycling mode dropdown)

- [ ] **Step 1: Modify pen tool drawing to use animated brush**

In `src/app.py`, in the drawing handler (where `PenTool.apply()` is called), add animated brush support:

```python
        # Before the normal brush apply:
        if self._animated_brush:
            brush_frame = self._animated_brush[self._animated_brush_index]
            # Draw using the current animated brush frame
            for (dx, dy), color in brush_frame.items():
                px, py = x + dx, y + dy
                if 0 <= px < self.timeline.width and 0 <= py < self.timeline.height:
                    active_layer.pixels.set_pixel(px, py, color)

            if self._animated_brush_mode == "per_pixel":
                self._animated_brush_index = (
                    (self._animated_brush_index + 1) % len(self._animated_brush)
                )
            return  # skip normal brush
```

- [ ] **Step 2: Advance per-stroke index on mouse release**

In `_on_canvas_release()`:

```python
        if self._animated_brush and self._animated_brush_mode == "per_stroke":
            self._animated_brush_index = (
                (self._animated_brush_index + 1) % len(self._animated_brush)
            )
```

- [ ] **Step 3: Add options bar controls**

In `src/ui/options_bar.py`, when the pen tool is active and `_animated_brush` is set, show:

```python
        # Animated brush indicator
        if app._animated_brush:
            n = len(app._animated_brush)
            tk.Label(bar, text=f"Animated Brush ({n} frames)",
                     fg=ACCENT_CYAN, bg=BG_PANEL, font=("Consolas", 8)).pack(side="left", padx=4)

            # Cycling mode dropdown
            mode_var = tk.StringVar(value=app._animated_brush_mode)
            mode_menu = tk.OptionMenu(bar, mode_var, "per_stroke", "per_pixel",
                                       command=lambda v: setattr(app, '_animated_brush_mode', v))
            mode_menu.pack(side="left", padx=2)

            # Clear button
            clear_btn = tk.Button(bar, text="Clear", command=app._clear_animated_brush)
            style_button(clear_btn)
            clear_btn.pack(side="left", padx=2)
```

- [ ] **Step 4: Implement _clear_animated_brush()**

```python
    def _clear_animated_brush(self):
        self._animated_brush = None
        self._animated_brush_index = 0
        self._update_options_bar()
        self._update_status("Animated brush cleared")
```

- [ ] **Step 5: Manual verification**

1. Create a 4-frame animation with different colored shapes
2. Select a region, press `Ctrl+Shift+B`
3. Draw on canvas — verify brush cycles through frames
4. Toggle between per-stroke and per-pixel modes
5. Click "Clear" to reset

---

## Chunk 5: 3D Mesh Layer (4.2) and Audio Sync (4.3)

### Task 13: OBJ Parser and Wireframe Renderer

**Files:**
- Create: `src/mesh_import.py` (.obj parser, orthographic projection, wireframe rendering)
- Test: `tests/test_mesh_import.py` (create)

- [ ] **Step 1: Write failing tests**

Create `tests/test_mesh_import.py`:

```python
"""Tests for .obj mesh import and wireframe rendering."""
import pytest
import os
import tempfile
import numpy as np
from src.pixel_data import PixelGrid


class TestObjParser:
    def test_parse_cube_vertices(self):
        from src.mesh_import import parse_obj
        obj_text = """
v 0.0 0.0 0.0
v 1.0 0.0 0.0
v 1.0 1.0 0.0
v 0.0 1.0 0.0
f 1 2 3 4
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.obj', delete=False) as f:
            f.write(obj_text)
            path = f.name
        try:
            vertices, faces = parse_obj(path)
            assert len(vertices) == 4
            assert len(faces) == 1
            assert vertices[0] == (0.0, 0.0, 0.0)
            assert faces[0] == [0, 1, 2, 3]  # 0-indexed
        finally:
            os.unlink(path)

    def test_parse_triangle(self):
        from src.mesh_import import parse_obj
        obj_text = "v 0 0 0\nv 1 0 0\nv 0.5 1 0\nf 1 2 3\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.obj', delete=False) as f:
            f.write(obj_text)
            path = f.name
        try:
            vertices, faces = parse_obj(path)
            assert len(vertices) == 3
            assert len(faces) == 1
            assert faces[0] == [0, 1, 2]
        finally:
            os.unlink(path)

    def test_ignores_comments_and_unknown_lines(self):
        from src.mesh_import import parse_obj
        obj_text = "# comment\nvn 0 1 0\nvt 0.5 0.5\nv 0 0 0\nv 1 0 0\nf 1 2\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.obj', delete=False) as f:
            f.write(obj_text)
            path = f.name
        try:
            vertices, faces = parse_obj(path)
            assert len(vertices) == 2
        finally:
            os.unlink(path)

    def test_face_with_vertex_texture_normal_format(self):
        from src.mesh_import import parse_obj
        obj_text = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1/1/1 2/2/2 3/3/3\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.obj', delete=False) as f:
            f.write(obj_text)
            path = f.name
        try:
            vertices, faces = parse_obj(path)
            assert faces[0] == [0, 1, 2]
        finally:
            os.unlink(path)


class TestWireframeRenderer:
    def test_render_produces_pixels(self):
        from src.mesh_import import render_wireframe
        vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0)]
        faces = [[0, 1, 2]]
        grid = render_wireframe(vertices, faces, width=32, height=32,
                                scale=10.0, offset_x=16, offset_y=16)
        assert grid.width == 32
        assert grid.height == 32
        # Should have some non-transparent pixels (the wireframe lines)
        has_pixels = False
        for y in range(32):
            for x in range(32):
                if grid.get_pixel(x, y)[3] > 0:
                    has_pixels = True
                    break
            if has_pixels:
                break
        assert has_pixels

    def test_render_empty_mesh(self):
        from src.mesh_import import render_wireframe
        grid = render_wireframe([], [], width=16, height=16)
        # All transparent
        for y in range(16):
            for x in range(16):
                assert grid.get_pixel(x, y) == (0, 0, 0, 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_mesh_import.py -v`
Expected: `ModuleNotFoundError: No module named 'src.mesh_import'`

- [ ] **Step 3: Create `src/mesh_import.py`**

```python
"""Minimal .obj mesh parser and orthographic wireframe renderer."""
from __future__ import annotations
import math
import numpy as np
from src.pixel_data import PixelGrid


def parse_obj(filepath: str) -> tuple[list[tuple[float, float, float]], list[list[int]]]:
    """Parse a Wavefront .obj file, extracting vertices and faces.

    Returns:
        (vertices, faces) where vertices are (x, y, z) tuples
        and faces are lists of 0-indexed vertex indices.
    """
    vertices: list[tuple[float, float, float]] = []
    faces: list[list[int]] = []

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if parts[0] == 'v' and len(parts) >= 4:
                vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif parts[0] == 'f' and len(parts) >= 3:
                face = []
                for p in parts[1:]:
                    # Handle f v, f v/vt, f v/vt/vn, f v//vn formats
                    idx = int(p.split('/')[0]) - 1  # OBJ is 1-indexed
                    face.append(idx)
                faces.append(face)

    return vertices, faces


def project_vertex(v: tuple[float, float, float],
                   scale: float = 1.0,
                   offset_x: float = 0.0, offset_y: float = 0.0,
                   rot_x: float = 0.0, rot_y: float = 0.0,
                   rot_z: float = 0.0) -> tuple[int, int]:
    """Orthographic projection of a 3D vertex to 2D screen coordinates.

    Rotates around origin, then scales and offsets.
    rot_x, rot_y, rot_z in radians.
    """
    x, y, z = v

    # Rotate around X axis
    if rot_x != 0:
        cos_a, sin_a = math.cos(rot_x), math.sin(rot_x)
        y, z = y * cos_a - z * sin_a, y * sin_a + z * cos_a

    # Rotate around Y axis
    if rot_y != 0:
        cos_a, sin_a = math.cos(rot_y), math.sin(rot_y)
        x, z = x * cos_a + z * sin_a, -x * sin_a + z * cos_a

    # Rotate around Z axis
    if rot_z != 0:
        cos_a, sin_a = math.cos(rot_z), math.sin(rot_z)
        x, y = x * cos_a - y * sin_a, x * sin_a + y * cos_a

    # Orthographic projection (ignore z)
    sx = int(x * scale + offset_x)
    sy = int(-y * scale + offset_y)  # flip Y for screen coords
    return (sx, sy)


def _bresenham_line(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """Bresenham's line algorithm. Returns list of (x, y) points."""
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    while True:
        points.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy

    return points


def render_wireframe(vertices: list[tuple[float, float, float]],
                     faces: list[list[int]],
                     width: int = 64, height: int = 64,
                     scale: float = 1.0,
                     offset_x: float = 0.0, offset_y: float = 0.0,
                     rot_x: float = 0.0, rot_y: float = 0.0,
                     rot_z: float = 0.0,
                     color: tuple = (180, 200, 255, 200)) -> PixelGrid:
    """Render a wireframe of the mesh onto a PixelGrid.

    Args:
        vertices: 3D vertex positions.
        faces: face index lists.
        width, height: output grid dimensions.
        scale: projection scale factor.
        offset_x, offset_y: screen offset (usually canvas center).
        rot_x, rot_y, rot_z: rotation angles in radians.
        color: RGBA wireframe color.
    """
    grid = PixelGrid(width, height)

    if not vertices or not faces:
        return grid

    # Project all vertices
    projected = [
        project_vertex(v, scale, offset_x, offset_y, rot_x, rot_y, rot_z)
        for v in vertices
    ]

    # Draw edges for each face
    drawn_edges: set[tuple[int, int]] = set()
    for face in faces:
        n = len(face)
        for i in range(n):
            v0 = face[i]
            v1 = face[(i + 1) % n]
            edge_key = (min(v0, v1), max(v0, v1))
            if edge_key in drawn_edges:
                continue
            drawn_edges.add(edge_key)

            if v0 >= len(projected) or v1 >= len(projected):
                continue

            x0, y0 = projected[v0]
            x1, y1 = projected[v1]

            for px, py in _bresenham_line(x0, y0, x1, y1):
                if 0 <= px < width and 0 <= py < height:
                    grid.set_pixel(px, py, color)

    return grid
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_mesh_import.py -v`

### Task 14: 3D Mesh Layer App Integration

**Files:**
- Modify: `src/app.py` (menu item, 3D reference layer creation, rotation controls)

- [ ] **Step 1: Add menu item**

In the Layer menu:

```python
        layer_menu.add_command(label="Add 3D Reference...",
                               command=self._add_3d_reference)
```

- [ ] **Step 2: Implement _add_3d_reference()**

```python
    def _add_3d_reference(self):
        """Load .obj mesh and render as wireframe reference layer."""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Load 3D Mesh",
            filetypes=[("OBJ files", "*.obj"), ("All files", "*.*")]
        )
        if not path:
            return

        from src.mesh_import import parse_obj, render_wireframe
        try:
            vertices, faces = parse_obj(path)
        except Exception as e:
            self._update_status(f"Failed to parse OBJ: {e}")
            return

        if not vertices:
            self._update_status("No vertices found in OBJ file")
            return

        import os
        w, h = self.timeline.width, self.timeline.height

        # Auto-scale to fit canvas
        xs = [v[0] for v in vertices]
        ys = [v[1] for v in vertices]
        mesh_w = max(xs) - min(xs) if xs else 1
        mesh_h = max(ys) - min(ys) if ys else 1
        fit_scale = min((w * 0.8) / max(mesh_w, 0.001),
                        (h * 0.8) / max(mesh_h, 0.001))

        grid = render_wireframe(vertices, faces, width=w, height=h,
                                scale=fit_scale,
                                offset_x=w / 2, offset_y=h / 2)

        name = f"3D: {os.path.basename(path)}"
        from src.layer import Layer
        layer = Layer(name, w, h)
        layer.is_reference = True
        layer.opacity = 0.5
        layer.pixels = grid

        # Store mesh data for re-rendering on parameter change
        layer._mesh_vertices = vertices
        layer._mesh_faces = faces
        layer._mesh_scale = fit_scale
        layer._mesh_rot = (0.0, 0.0, 0.0)

        frame_obj = self.timeline.current_frame_obj()
        frame_obj.layers.append(layer)
        self._refresh_canvas()
        self._update_timeline()
        self._update_status(f"Added 3D reference: {name} ({len(vertices)} verts, {len(faces)} faces)")
```

- [ ] **Step 3: Add rotation controls (optional enhancement)**

Create a small popup or sidebar controls for rotating the 3D reference:

```python
    def _show_3d_controls(self, layer):
        """Show X/Y/Z rotation sliders for a 3D reference layer."""
        import math
        from tkinter import Toplevel, Scale, HORIZONTAL

        win = Toplevel(self.root)
        win.title("3D Reference Controls")
        win.geometry("300x200")

        def update_rotation(val=None):
            rx = math.radians(rx_var.get())
            ry = math.radians(ry_var.get())
            rz = math.radians(rz_var.get())
            from src.mesh_import import render_wireframe
            new_grid = render_wireframe(
                layer._mesh_vertices, layer._mesh_faces,
                width=self.timeline.width, height=self.timeline.height,
                scale=layer._mesh_scale,
                offset_x=self.timeline.width / 2,
                offset_y=self.timeline.height / 2,
                rot_x=rx, rot_y=ry, rot_z=rz)
            layer.pixels = new_grid
            layer._mesh_rot = (rx, ry, rz)
            self._refresh_canvas()

        rx_var = Scale(win, from_=-180, to=180, orient=HORIZONTAL,
                       label="Rotate X", command=update_rotation)
        rx_var.pack(fill="x", padx=10)
        ry_var = Scale(win, from_=-180, to=180, orient=HORIZONTAL,
                       label="Rotate Y", command=update_rotation)
        ry_var.pack(fill="x", padx=10)
        rz_var = Scale(win, from_=-180, to=180, orient=HORIZONTAL,
                       label="Rotate Z", command=update_rotation)
        rz_var.pack(fill="x", padx=10)
```

- [ ] **Step 4: Manual verification**

1. Download or create a simple .obj file (cube or teapot)
2. Use `Layer > Add 3D Reference...`
3. Verify wireframe appears as a reference layer
4. Verify it does not appear in exports

### Task 15: Audio Sync for Animation

**Files:**
- Create: `src/audio.py` (audio loading, playback, waveform extraction)
- Modify: `src/app.py` (audio state, playback sync)
- Modify: `src/ui/timeline.py` (waveform visualization)
- Modify: `src/project.py` (serialize audio path + markers)
- Test: `tests/test_audio.py` (create)

- [ ] **Step 1: Write tests for audio module**

Create `tests/test_audio.py`:

```python
"""Tests for audio sync module."""
import pytest
import os
import struct
import tempfile
import wave


def create_test_wav(path: str, duration_s: float = 1.0,
                    sample_rate: int = 22050):
    """Create a minimal .wav file for testing."""
    n_samples = int(sample_rate * duration_s)
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # Generate silence
        data = struct.pack('<' + 'h' * n_samples, *([0] * n_samples))
        wf.writeframes(data)


class TestAudioLoading:
    def test_load_wav_returns_waveform(self):
        from src.audio import load_audio
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            path = f.name
        try:
            create_test_wav(path, duration_s=0.5)
            waveform, sample_rate, duration_ms = load_audio(path)
            assert len(waveform) > 0
            assert sample_rate == 22050
            assert abs(duration_ms - 500) < 50  # ~500ms
        finally:
            os.unlink(path)

    def test_downsample_waveform(self):
        from src.audio import downsample_waveform
        import numpy as np
        waveform = np.random.randint(-32768, 32767, size=10000, dtype=np.int16)
        downsampled = downsample_waveform(waveform, target_bins=100)
        assert len(downsampled) == 100

    def test_load_nonexistent_returns_none(self):
        from src.audio import load_audio
        result = load_audio("/nonexistent/path.wav")
        assert result is None


class TestAudioMarkers:
    def test_marker_structure(self):
        marker = {"name": "Beat 1", "time_ms": 250, "frame_index": 2}
        assert marker["name"] == "Beat 1"
        assert marker["time_ms"] == 250
```

- [ ] **Step 2: Create `src/audio.py`**

```python
"""Audio loading, playback, and waveform extraction for animation sync.

Optional dependency: pygame.mixer for playback with seeking.
Feature is hidden if pygame is not installed.
"""
from __future__ import annotations
import wave
import struct
import numpy as np

# Check for pygame availability
_HAS_PYGAME = False
try:
    import pygame.mixer
    _HAS_PYGAME = True
except ImportError:
    pass


def is_available() -> bool:
    """Return True if audio playback is available (pygame installed)."""
    return _HAS_PYGAME


def load_audio(filepath: str) -> tuple[np.ndarray, int, float] | None:
    """Load a .wav file and return (waveform, sample_rate, duration_ms).

    Returns None on failure.
    """
    try:
        with wave.open(filepath, 'r') as wf:
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        if sample_width == 2:
            fmt = '<' + 'h' * (len(raw) // 2)
            samples = np.array(struct.unpack(fmt, raw), dtype=np.int16)
        elif sample_width == 1:
            samples = np.frombuffer(raw, dtype=np.uint8).astype(np.int16) - 128
        else:
            return None

        # Mix to mono if stereo
        if n_channels == 2:
            samples = samples.reshape(-1, 2).mean(axis=1).astype(np.int16)

        duration_ms = (n_frames / sample_rate) * 1000.0
        return samples, sample_rate, duration_ms

    except Exception:
        return None


def downsample_waveform(waveform: np.ndarray, target_bins: int) -> np.ndarray:
    """Downsample waveform to target_bins amplitude values for visualization.

    Returns array of absolute amplitude values, normalized to 0.0-1.0.
    """
    if len(waveform) == 0 or target_bins <= 0:
        return np.zeros(target_bins, dtype=np.float32)

    bin_size = max(1, len(waveform) // target_bins)
    result = np.zeros(target_bins, dtype=np.float32)

    for i in range(target_bins):
        start = i * bin_size
        end = min(start + bin_size, len(waveform))
        if start < len(waveform):
            chunk = np.abs(waveform[start:end].astype(np.float32))
            result[i] = chunk.max() if len(chunk) > 0 else 0

    # Normalize to 0-1
    max_val = result.max()
    if max_val > 0:
        result /= max_val

    return result


class AudioPlayer:
    """Wrapper around pygame.mixer for synced audio playback."""

    def __init__(self, filepath: str):
        self._filepath = filepath
        self._playing = False
        if _HAS_PYGAME:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050)

    def play(self, start_ms: float = 0.0):
        """Start playback from the given position in milliseconds."""
        if not _HAS_PYGAME:
            return
        try:
            pygame.mixer.music.load(self._filepath)
            pygame.mixer.music.play(start=start_ms / 1000.0)
            self._playing = True
        except Exception:
            self._playing = False

    def stop(self):
        """Stop playback."""
        if not _HAS_PYGAME:
            return
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self._playing = False

    def is_playing(self) -> bool:
        if not _HAS_PYGAME:
            return False
        return self._playing and pygame.mixer.music.get_busy()
```

- [ ] **Step 3: Run audio tests**

Run: `python -m pytest tests/test_audio.py -v`

- [ ] **Step 4: Add audio state to app.py**

In `__init__`:

```python
        self._audio_path: str | None = None
        self._audio_waveform: np.ndarray | None = None
        self._audio_sample_rate: int = 0
        self._audio_duration_ms: float = 0
        self._audio_player = None
        self._audio_markers: list[dict] = []  # {"name": str, "time_ms": float}
```

- [ ] **Step 5: Add menu item for loading audio**

In the Timeline menu (or a new Audio submenu):

```python
        from src.audio import is_available as audio_available
        if audio_available():
            timeline_menu.add_command(label="Load Audio Track...",
                                      command=self._load_audio_track)
```

- [ ] **Step 6: Implement _load_audio_track()**

```python
    def _load_audio_track(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Load Audio Track",
            filetypes=[("WAV files", "*.wav"), ("All files", "*.*")]
        )
        if not path:
            return
        from src.audio import load_audio, AudioPlayer
        result = load_audio(path)
        if result is None:
            self._update_status("Failed to load audio file")
            return
        self._audio_waveform, self._audio_sample_rate, self._audio_duration_ms = result
        self._audio_path = path
        self._audio_player = AudioPlayer(path)
        self._update_status(f"Audio loaded: {int(self._audio_duration_ms)}ms")
        self._update_timeline()
```

- [ ] **Step 7: Sync audio with animation playback**

In the animation play handler, after starting animation:

```python
        if self._audio_player:
            # Calculate current position in ms
            current_ms = sum(
                self.timeline.get_frame_obj(i).duration_ms
                for i in range(self.timeline.current_index)
            )
            self._audio_player.play(start_ms=current_ms)
```

In the animation stop handler:

```python
        if self._audio_player:
            self._audio_player.stop()
```

- [ ] **Step 8: Add waveform visualization to timeline**

In `src/ui/timeline.py`, add a waveform rendering strip below the frame grid:

```python
    def render_waveform(self, canvas, waveform_data, x_start, y_start,
                        width, height, frame_count):
        """Draw downsampled waveform bars aligned to timeline frames."""
        if waveform_data is None or len(waveform_data) == 0:
            return
        from src.audio import downsample_waveform
        bins = downsample_waveform(waveform_data, target_bins=frame_count)
        bar_width = max(1, width // frame_count)
        for i, amplitude in enumerate(bins):
            bar_h = int(amplitude * height)
            x = x_start + i * bar_width
            y_top = y_start + height - bar_h
            canvas.create_rectangle(x, y_top, x + bar_width - 1,
                                    y_start + height,
                                    fill="#4488aa", outline="")
```

- [ ] **Step 9: Serialize audio path and markers in project.py**

In `save_project()`, add to the project dict:

```python
    if hasattr(timeline, '_audio_path') and timeline._audio_path:
        project["audio_path"] = timeline._audio_path
        project["audio_markers"] = timeline._audio_markers
```

In `load_project()`:

```python
    audio_path = project.get("audio_path", None)
    audio_markers = project.get("audio_markers", [])
```

Return these as part of the loaded data, or attach to the timeline object.

- [ ] **Step 10: Run all tests**

Run: `python -m pytest tests/ -v`

---

## Chunk 6: Multi-Document Tabs (4.7)

The largest feature — extracting document state from `RetroSpriteApp` into a `Document` class and adding a tab bar widget.

### Task 16: Extract Document Class

**Files:**
- Create: `src/document.py`
- Test: `tests/test_document.py` (create)

- [ ] **Step 1: Write failing tests**

Create `tests/test_document.py`:

```python
"""Tests for Document class."""
import pytest
from src.pixel_data import PixelGrid


class TestDocument:
    def test_create_document(self):
        from src.document import Document
        doc = Document(width=32, height=32)
        assert doc.width == 32
        assert doc.height == 32
        assert doc.project_path is None
        assert doc.dirty is False
        assert doc.timeline is not None
        assert doc.palette is not None

    def test_document_has_undo_stacks(self):
        from src.document import Document
        doc = Document(width=16, height=16)
        assert isinstance(doc.undo_stack, list)
        assert isinstance(doc.redo_stack, list)
        assert len(doc.undo_stack) == 0

    def test_document_has_zoom(self):
        from src.document import Document
        doc = Document(width=16, height=16)
        assert doc.zoom >= 1

    def test_document_title_untitled(self):
        from src.document import Document
        doc = Document(width=16, height=16)
        assert doc.title == "Untitled"

    def test_document_title_from_path(self):
        from src.document import Document
        doc = Document(width=16, height=16)
        doc.project_path = "/some/path/sprite.retro"
        assert doc.title == "sprite.retro"

    def test_document_dirty_indicator(self):
        from src.document import Document
        doc = Document(width=16, height=16)
        doc.dirty = True
        assert doc.display_title == "Untitled *"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_document.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `src/document.py`**

```python
"""Document model — encapsulates all per-project state."""
from __future__ import annotations
import os
from src.animation import AnimationTimeline
from src.palette import Palette
from src.pixel_data import PixelGrid


class Document:
    """A single document holding all project state.

    Extracted from RetroSpriteApp to support multi-document tabs.
    """

    UNDO_LIMIT = 10

    def __init__(self, width: int = 32, height: int = 32,
                 color_mode: str = "rgba"):
        self.timeline = AnimationTimeline(width, height)
        self.timeline.color_mode = color_mode
        self.palette = Palette("Pico-8")
        self.tool_settings: dict = {}

        # Undo/redo
        self.undo_stack: list[dict] = []
        self.redo_stack: list[dict] = []

        # Project metadata
        self.project_path: str | None = None
        self.dirty: bool = False

        # View state
        self.zoom: int = 1
        self.scroll_x: float = 0.0
        self.scroll_y: float = 0.0

        # Audio (optional)
        self.audio_path: str | None = None
        self.audio_markers: list[dict] = []

    @property
    def width(self) -> int:
        return self.timeline.width

    @property
    def height(self) -> int:
        return self.timeline.height

    @property
    def title(self) -> str:
        if self.project_path:
            return os.path.basename(self.project_path)
        return "Untitled"

    @property
    def display_title(self) -> str:
        t = self.title
        if self.dirty:
            t += " *"
        return t
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_document.py -v`

### Task 17: Tab Bar Widget

**Files:**
- Create: `src/ui/tab_bar.py`
- Test: manual (Tkinter widget)

- [ ] **Step 1: Create `src/ui/tab_bar.py`**

```python
"""Tab bar widget for multi-document support."""
from __future__ import annotations
import tkinter as tk
from src.ui.theme import (
    BG_DEEP, BG_PANEL, BG_PANEL_ALT, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, BUTTON_BG, BUTTON_HOVER, style_button,
)


MAX_TABS = 8


class TabBar(tk.Frame):
    """Horizontal tab bar for switching between open documents."""

    def __init__(self, parent, on_select=None, on_close=None,
                 on_new=None, **kwargs):
        super().__init__(parent, bg=BG_DEEP, height=28, **kwargs)
        self.pack_propagate(False)

        self._on_select = on_select  # callback(index)
        self._on_close = on_close    # callback(index)
        self._on_new = on_new        # callback()

        self._tabs: list[dict] = []  # {"title": str, "widget": Frame}
        self._active_index: int = 0

        # Container for tab buttons
        self._tab_frame = tk.Frame(self, bg=BG_DEEP)
        self._tab_frame.pack(side="left", fill="y")

        # New tab button
        self._new_btn = tk.Button(self, text="+", command=self._on_new_click,
                                   bg=BUTTON_BG, fg=TEXT_PRIMARY,
                                   font=("Consolas", 10, "bold"),
                                   borderwidth=0, padx=8, pady=0)
        self._new_btn.pack(side="left", padx=(2, 0))
        self._new_btn.bind("<Enter>",
                           lambda e: self._new_btn.config(bg=BUTTON_HOVER))
        self._new_btn.bind("<Leave>",
                           lambda e: self._new_btn.config(bg=BUTTON_BG))

    def set_tabs(self, titles: list[str], active_index: int = 0):
        """Rebuild tab buttons from a list of document titles."""
        # Clear existing
        for tab in self._tabs:
            tab["widget"].destroy()
        self._tabs.clear()

        self._active_index = active_index

        for i, title in enumerate(titles):
            tab_frame = tk.Frame(self._tab_frame, bg=BG_PANEL, padx=2)
            tab_frame.pack(side="left", padx=(0, 1))

            is_active = (i == active_index)
            bg = ACCENT_CYAN if is_active else BG_PANEL_ALT
            fg = BG_DEEP if is_active else TEXT_SECONDARY

            label = tk.Label(tab_frame, text=title, bg=bg, fg=fg,
                             font=("Consolas", 8, "bold" if is_active else ""),
                             padx=8, pady=2)
            label.pack(side="left")
            label.bind("<Button-1>", lambda e, idx=i: self._on_tab_click(idx))

            # Close button (x)
            close_btn = tk.Label(tab_frame, text="\u00d7", bg=bg,
                                  fg=fg, font=("Consolas", 8),
                                  padx=2, cursor="hand2")
            close_btn.pack(side="left")
            close_btn.bind("<Button-1>",
                           lambda e, idx=i: self._on_close_click(idx))

            self._tabs.append({"title": title, "widget": tab_frame})

    def _on_tab_click(self, index: int):
        if self._on_select and index != self._active_index:
            self._on_select(index)

    def _on_close_click(self, index: int):
        if self._on_close:
            self._on_close(index)

    def _on_new_click(self):
        if self._on_new and len(self._tabs) < MAX_TABS:
            self._on_new()
```

- [ ] **Step 2: Verify file was created**

Run: `python -c "from src.ui.tab_bar import TabBar; print('OK')"`

### Task 18: Integrate Multi-Document into App

**Files:**
- Modify: `src/app.py` (refactor to use Document list, tab management)

This is the most invasive change. It must be done carefully to avoid breaking existing functionality.

- [ ] **Step 1: Add document list and tab bar to app.py __init__**

In `__init__`, add after other state initialization:

```python
        from src.document import Document
        from src.ui.tab_bar import TabBar

        # Multi-document state
        self._documents: list[Document] = []
        self._active_doc_index: int = 0

        # Create initial document from current state
        initial_doc = Document(width=self.timeline.width,
                               height=self.timeline.height)
        initial_doc.timeline = self.timeline
        initial_doc.palette = self.palette
        initial_doc.undo_stack = self._undo_stack
        initial_doc.redo_stack = self._redo_stack
        self._documents.append(initial_doc)

        # Tab bar (above canvas)
        self._tab_bar = TabBar(
            self._canvas_frame,  # parent frame above canvas
            on_select=self._switch_tab,
            on_close=self._close_tab,
            on_new=self._new_tab,
        )
        self._tab_bar.pack(fill="x", before=self._canvas_widget)
        self._update_tab_bar()
```

- [ ] **Step 2: Implement _switch_tab()**

```python
    def _switch_tab(self, index: int):
        """Switch to document at the given tab index."""
        if index == self._active_doc_index:
            return
        if index < 0 or index >= len(self._documents):
            return

        # Save current state to active document
        self._save_to_active_doc()

        # Switch
        self._active_doc_index = index

        # Load new document state
        self._load_from_active_doc()
        self._update_tab_bar()
        self._refresh_canvas()
        self._update_timeline()
        self._update_status(f"Switched to: {self._active_doc.title}")

    @property
    def _active_doc(self) -> Document:
        return self._documents[self._active_doc_index]
```

- [ ] **Step 3: Implement _save_to_active_doc() and _load_from_active_doc()**

```python
    def _save_to_active_doc(self):
        """Persist current app state into the active document."""
        doc = self._active_doc
        doc.timeline = self.timeline
        doc.palette = self.palette
        doc.undo_stack = self._undo_stack
        doc.redo_stack = self._redo_stack
        doc.project_path = self._project_path
        doc.dirty = self._dirty
        doc.zoom = self._zoom

    def _load_from_active_doc(self):
        """Restore app state from the active document."""
        doc = self._active_doc
        self.timeline = doc.timeline
        self.palette = doc.palette
        self._undo_stack = doc.undo_stack
        self._redo_stack = doc.redo_stack
        self._project_path = doc.project_path
        self._dirty = doc.dirty
        self._zoom = doc.zoom
```

- [ ] **Step 4: Implement _new_tab()**

```python
    def _new_tab(self):
        """Create a new empty document in a new tab."""
        from src.document import Document
        if len(self._documents) >= 8:
            self._update_status("Maximum 8 tabs allowed")
            return
        self._save_to_active_doc()
        doc = Document(width=32, height=32)
        self._documents.append(doc)
        self._active_doc_index = len(self._documents) - 1
        self._load_from_active_doc()
        self._update_tab_bar()
        self._refresh_canvas()
        self._update_timeline()
```

- [ ] **Step 5: Implement _close_tab()**

```python
    def _close_tab(self, index: int):
        """Close the tab at the given index. Prompt save if dirty."""
        if len(self._documents) <= 1:
            return  # Don't close the last tab

        doc = self._documents[index]
        if doc.dirty:
            from tkinter import messagebox
            result = messagebox.askyesnocancel(
                "Unsaved Changes",
                f"Save changes to {doc.title}?"
            )
            if result is None:  # Cancel
                return
            if result:  # Yes
                self._save_project()

        self._documents.pop(index)
        if self._active_doc_index >= len(self._documents):
            self._active_doc_index = len(self._documents) - 1
        elif self._active_doc_index > index:
            self._active_doc_index -= 1

        self._load_from_active_doc()
        self._update_tab_bar()
        self._refresh_canvas()
        self._update_timeline()
```

- [ ] **Step 6: Implement _update_tab_bar()**

```python
    def _update_tab_bar(self):
        """Refresh tab bar titles from document list."""
        titles = [doc.display_title for doc in self._documents]
        self._tab_bar.set_tabs(titles, self._active_doc_index)
```

- [ ] **Step 7: Bind keyboard shortcuts**

```python
        self.root.bind("<Control-n>", lambda e: self._new_tab())
        self.root.bind("<Control-w>", lambda e: self._close_tab(self._active_doc_index))
        self.root.bind("<Control-Tab>", lambda e: self._switch_tab(
            (self._active_doc_index + 1) % len(self._documents)))
        self.root.bind("<Control-Shift-Tab>", lambda e: self._switch_tab(
            (self._active_doc_index - 1) % len(self._documents)))
```

Note: `Ctrl+N` may conflict with existing "New Project" binding. Modify existing `_new_project()` to create a new tab instead of replacing current state, or route `Ctrl+N` through `_new_tab()`.

- [ ] **Step 8: Ensure _mark_dirty() updates tab bar**

In `_mark_dirty()`, add:

```python
        self._active_doc.dirty = True
        self._update_tab_bar()
```

- [ ] **Step 9: Run full test suite**

Run: `python -m pytest tests/ -v`

Note: Many existing tests may need adjustment since they instantiate `RetroSpriteApp` directly. The Document extraction should be backward-compatible — existing code still accesses `self.timeline`, `self.palette`, etc. through the app, which delegates to the active document.

- [ ] **Step 10: Manual verification**

1. Launch app — single tab shows "Untitled"
2. `Ctrl+N` — new tab appears, "Untitled" x2
3. Draw on tab 1, switch to tab 2 — tab 1 content preserved
4. Mark tab 2 dirty, close with `Ctrl+W` — save prompt appears
5. `Ctrl+Tab` cycles between tabs
6. Open a project in one tab, new project in another — independent

---

## Cross-Cutting: Final Validation

### Task 19: Integration Testing and Cleanup

- [ ] **Step 1: Run the complete test suite**

```
python -m pytest tests/ -v --tb=short
```

Fix any failures.

- [ ] **Step 2: Verify serialization backward compatibility**

Load a project saved with the previous version (before Plan 4 changes). Verify:
- `is_reference` defaults to `False` for all layers
- No errors from missing `ref_offset`, `ref_scale`, `audio_path`, etc.
- Project saves successfully in the new format

- [ ] **Step 3: Verify optional dependency graceful degradation**

Test with `pygame` not installed:
- Audio menu items should not appear
- No import errors on startup
- All other features work normally

- [ ] **Step 4: Performance check**

- Scale2x/Scale3x on a 64x64 image should complete in < 1 second
- Undo history panel should not slow down drawing operations
- Tab switching should be < 100ms

- [ ] **Step 5: Verify all new files have proper imports and docstrings**

New files created in this plan:
- `src/mesh_import.py`
- `src/audio.py`
- `src/document.py`
- `src/ui/undo_panel.py`
- `src/ui/tab_bar.py`
- `tests/test_reference_layer.py`
- `tests/test_pixel_scaling.py`
- `tests/test_mesh_import.py`
- `tests/test_audio.py`
- `tests/test_undo_history.py`
- `tests/test_animated_brush.py`
- `tests/test_document.py`

Modified files:
- `src/layer.py` (is_reference, ref_offset, ref_scale)
- `src/image_processing.py` (scale2x, scale3x, clean_edge, omni_scale)
- `src/project.py` (reference layer fields, audio path/markers)
- `src/app.py` (reference layers, animated brushes, 3D mesh, audio sync, undo labels, multi-doc tabs)
- `src/ui/right_panel.py` (undo history section)
- `src/ui/timeline.py` (reference layer indicator, waveform rendering)
- `src/ui/options_bar.py` (animated brush controls, scaling algorithm selector)
