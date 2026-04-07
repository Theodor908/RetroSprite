# Batch 4: Advanced Tools Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add RotSprite rotation, 7 non-destructive layer effects, and tilemap layers to RetroSprite.

**Architecture:** Three independent features sharing the same rendering pipeline. Layer effects add an `effects` list to `Layer` and an `apply_effects()` call in `flatten_layers()`. Tilemap layers add a `TilemapLayer` subclass whose `pixels` property auto-renders tile grids. RotSprite is a standalone algorithm module wired into an interactive canvas tool.

**Tech Stack:** Python 3.8+, NumPy, Tkinter, Pillow, pytest

**Spec:** `docs/superpowers/specs/2026-03-11-batch4-advanced-tools-design.md`

---

## Chunk 1: RotSprite Rotation

### Task 1: RotSprite Algorithm — Core Functions

**Files:**
- Create: `src/rotsprite.py`
- Create: `tests/test_rotsprite.py`

- [ ] **Step 1: Write failing tests for color_distance and scale2x**

```python
# tests/test_rotsprite.py
import numpy as np
from src.rotsprite import color_distance, scale2x, rotsprite_rotate, fast_rotate


class TestColorDistance:
    def test_identical_colors(self):
        assert color_distance((255, 0, 0, 255), (255, 0, 0, 255)) == 0

    def test_different_colors(self):
        assert color_distance((255, 0, 0, 255), (0, 0, 0, 255)) == 255

    def test_full_distance(self):
        assert color_distance((0, 0, 0, 0), (255, 255, 255, 255)) == 1020

    def test_partial_distance(self):
        assert color_distance((100, 100, 100, 255), (110, 90, 100, 255)) == 20


class TestScale2x:
    def test_single_pixel(self):
        pixels = np.zeros((1, 1, 4), dtype=np.uint8)
        pixels[0, 0] = [255, 0, 0, 255]
        result = scale2x(pixels)
        assert result.shape == (2, 2, 4)
        assert np.all(result[:, :, 0] == 255)

    def test_uniform_2x2(self):
        pixels = np.full((2, 2, 4), [0, 255, 0, 255], dtype=np.uint8)
        result = scale2x(pixels)
        assert result.shape == (4, 4, 4)
        assert np.all(result[:, :, 1] == 255)

    def test_edge_detection(self):
        """Scale2x should smooth diagonal edges."""
        pixels = np.zeros((3, 3, 4), dtype=np.uint8)
        pixels[0, 0] = [255, 255, 255, 255]
        pixels[1, 1] = [255, 255, 255, 255]
        pixels[2, 2] = [255, 255, 255, 255]
        result = scale2x(pixels)
        assert result.shape == (6, 6, 4)
        # The diagonal should be smoothed — at least some new white pixels added
        white_count_orig = 3
        white_count_result = np.sum(result[:, :, 3] > 0)
        assert white_count_result > white_count_orig
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_rotsprite.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement color_distance and scale2x**

```python
# src/rotsprite.py
"""RotSprite pixel-art-aware rotation algorithm."""
from __future__ import annotations
import numpy as np
from PIL import Image
from src.pixel_data import PixelGrid


def color_distance(a: tuple, b: tuple) -> int:
    """Manhattan distance in RGBA space between two color tuples."""
    return sum(abs(int(a[i]) - int(b[i])) for i in range(4))


def scale2x(pixels: np.ndarray, threshold: int = 48) -> np.ndarray:
    """Modified Scale2x with similarity threshold for RotSprite.

    Input: (H, W, 4) uint8 RGBA array.
    Output: (H*2, W*2, 4) uint8 RGBA array.
    """
    h, w = pixels.shape[:2]
    result = np.zeros((h * 2, w * 2, 4), dtype=np.uint8)

    # Pad pixels with edge values for border handling
    padded = np.pad(pixels, ((1, 1), (1, 1), (0, 0)), mode='edge')

    # Extract neighbors: A=top-left, B=top, C=top-right, D=left, E=center,
    # F=right, G=bot-left, H=bot, I=bot-right
    B = padded[0:h, 1:w+1]    # top
    D = padded[1:h+1, 0:w]    # left
    E = padded[1:h+1, 1:w+1]  # center (= original pixels)
    F = padded[1:h+1, 2:w+2]  # right
    H = padded[2:h+2, 1:w+1]  # bottom

    # Compute similarity masks using Manhattan distance
    def similar(a, b):
        diff = np.sum(np.abs(a.astype(np.int16) - b.astype(np.int16)), axis=-1)
        return diff < threshold

    def not_similar(a, b):
        diff = np.sum(np.abs(a.astype(np.int16) - b.astype(np.int16)), axis=-1)
        return diff >= threshold

    # Scale2x rules:
    # E0 = D if (D≈B and D≉H and B≉F) else E
    # E1 = F if (B≈F and B≉D and F≉H) else E
    # E2 = D if (D≈H and D≉B and H≉F) else E
    # E3 = F if (H≈F and H≉D and F≉B) else E

    cond0 = similar(D, B) & not_similar(D, H) & not_similar(B, F)
    cond1 = similar(B, F) & not_similar(B, D) & not_similar(F, H)
    cond2 = similar(D, H) & not_similar(D, B) & not_similar(H, F)
    cond3 = similar(H, F) & not_similar(H, D) & not_similar(F, B)

    # Expand condition masks for RGBA channels
    cond0 = cond0[:, :, np.newaxis]
    cond1 = cond1[:, :, np.newaxis]
    cond2 = cond2[:, :, np.newaxis]
    cond3 = cond3[:, :, np.newaxis]

    result[0::2, 0::2] = np.where(cond0, D, E)  # E0
    result[0::2, 1::2] = np.where(cond1, F, E)  # E1
    result[1::2, 0::2] = np.where(cond2, D, E)  # E2
    result[1::2, 1::2] = np.where(cond3, F, E)  # E3

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_rotsprite.py::TestColorDistance tests/test_rotsprite.py::TestScale2x -v`
Expected: PASS

- [ ] **Step 5: Write failing tests for rotsprite_rotate and fast_rotate**

Add to `tests/test_rotsprite.py`:

```python
class TestFastRotate:
    def test_90_degrees(self):
        pixels = np.zeros((4, 4, 4), dtype=np.uint8)
        pixels[0, :] = [255, 0, 0, 255]  # red top row
        result = fast_rotate(pixels, 90)
        assert result.shape == (4, 4, 4)
        # After 90° CW rotation, top row should become right column
        assert np.all(result[:, 3, 0] == 255)

    def test_0_degrees_identity(self):
        pixels = np.zeros((4, 4, 4), dtype=np.uint8)
        pixels[1, 2] = [0, 255, 0, 255]
        result = fast_rotate(pixels, 0)
        assert np.array_equal(result, pixels)

    def test_360_degrees_identity(self):
        pixels = np.zeros((4, 4, 4), dtype=np.uint8)
        pixels[1, 2] = [0, 255, 0, 255]
        result = fast_rotate(pixels, 360)
        assert np.array_equal(result, pixels)

    def test_custom_pivot(self):
        pixels = np.zeros((8, 8, 4), dtype=np.uint8)
        pixels[0, 0] = [255, 0, 0, 255]
        result = fast_rotate(pixels, 90, pivot=(0, 0))
        assert result.shape == (8, 8, 4)


class TestRotspriteRotate:
    def test_90_degrees_preserves_shape(self):
        pixels = np.zeros((8, 8, 4), dtype=np.uint8)
        pixels[0, :] = [255, 0, 0, 255]  # red top row
        result = rotsprite_rotate(pixels, 90)
        assert result.shape == (8, 8, 4)

    def test_0_degrees_identity(self):
        pixels = np.zeros((8, 8, 4), dtype=np.uint8)
        pixels[2, 3] = [0, 255, 0, 255]
        result = rotsprite_rotate(pixels, 0)
        # Should be essentially identical at 0 degrees
        assert result[2, 3, 1] == 255

    def test_no_new_colors(self):
        """RotSprite should not introduce colors not in the original."""
        pixels = np.zeros((8, 8, 4), dtype=np.uint8)
        pixels[2:6, 2:6] = [255, 0, 0, 255]  # red square
        result = rotsprite_rotate(pixels, 45)
        # Every non-transparent pixel should be red
        opaque = result[:, :, 3] > 0
        if np.any(opaque):
            assert np.all(result[opaque, 0] == 255)
            assert np.all(result[opaque, 1] == 0)
            assert np.all(result[opaque, 2] == 0)
```

- [ ] **Step 6: Implement rotsprite_rotate and fast_rotate**

Add to `src/rotsprite.py`:

```python
def fast_rotate(pixels: np.ndarray, angle: float,
                pivot: tuple[int, int] | None = None) -> np.ndarray:
    """Simple nearest-neighbor rotation via PIL.

    Args:
        pixels: (H, W, 4) uint8 RGBA array
        angle: rotation angle in degrees (clockwise)
        pivot: rotation center (x, y). Defaults to image center.
    Returns:
        Rotated (H, W, 4) uint8 array, clipped to original bounds.
    """
    if angle % 360 == 0:
        return pixels.copy()
    img = Image.fromarray(pixels, "RGBA")
    if pivot is not None:
        # PIL rotates around center; translate to pivot, rotate, translate back
        cx, cy = img.width / 2, img.height / 2
        px, py = pivot
        dx, dy = cx - px, cy - py
        from PIL import ImageTransform
        import math
        rad = math.radians(-angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        # Affine transform: translate(-pivot) -> rotate -> translate(+pivot)
        # Combined into single affine matrix
        a = cos_a
        b = sin_a
        c = px - cos_a * px - sin_a * py
        d = -sin_a
        e = cos_a
        f_val = py + sin_a * px - cos_a * py
        rotated = img.transform(img.size, Image.AFFINE,
                                (a, b, c, d, e, f_val),
                                resample=Image.NEAREST)
    else:
        rotated = img.rotate(-angle, resample=Image.NEAREST, expand=False)
    return np.array(rotated, dtype=np.uint8)


def _mode_downsample(pixels: np.ndarray, factor: int) -> np.ndarray:
    """Downsample by taking the most common color in each block.

    This avoids introducing new colors via averaging.
    """
    h, w = pixels.shape[:2]
    new_h, new_w = h // factor, w // factor
    result = np.zeros((new_h, new_w, 4), dtype=np.uint8)

    for y in range(new_h):
        for x in range(new_w):
            block = pixels[y*factor:(y+1)*factor, x*factor:(x+1)*factor]
            # Flatten block to list of RGBA tuples, find mode
            flat = block.reshape(-1, 4)
            # Find most common non-transparent color
            opaque = flat[flat[:, 3] > 0]
            if len(opaque) == 0:
                continue
            # Use simple approach: pack RGBA to uint32, find mode
            packed = (opaque[:, 0].astype(np.uint32) << 24 |
                      opaque[:, 1].astype(np.uint32) << 16 |
                      opaque[:, 2].astype(np.uint32) << 8 |
                      opaque[:, 3].astype(np.uint32))
            values, counts = np.unique(packed, return_counts=True)
            mode_packed = values[np.argmax(counts)]
            result[y, x] = [
                (mode_packed >> 24) & 0xFF,
                (mode_packed >> 16) & 0xFF,
                (mode_packed >> 8) & 0xFF,
                mode_packed & 0xFF,
            ]
    return result


def rotsprite_rotate(pixels: np.ndarray, angle: float,
                     pivot: tuple[int, int] | None = None) -> np.ndarray:
    """RotSprite rotation: 3x Scale2x (8x) -> rotate -> mode downsample.

    Args:
        pixels: (H, W, 4) uint8 RGBA array
        angle: rotation angle in degrees (clockwise)
        pivot: rotation center (x, y). Defaults to image center.
    Returns:
        Rotated (H, W, 4) uint8 array, same dimensions as input.
    """
    if angle % 360 == 0:
        return pixels.copy()

    # Step 1: Scale up 8x with modified Scale2x (3 passes)
    upscaled = pixels
    for _ in range(3):
        upscaled = scale2x(upscaled)

    # Step 2: Rotate at 8x resolution (nearest neighbor)
    pivot_8x = None
    if pivot is not None:
        pivot_8x = (pivot[0] * 8, pivot[1] * 8)
    rotated = fast_rotate(upscaled, angle, pivot=pivot_8x)

    # Step 3: Downsample back to original size
    result = _mode_downsample(rotated, 8)

    return result
```

- [ ] **Step 7: Run all rotsprite tests**

Run: `python -m pytest tests/test_rotsprite.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/rotsprite.py tests/test_rotsprite.py
git commit -m "feat: add RotSprite algorithm with Scale2x, fast_rotate, mode downsample"
```

---

### Task 2: Wire RotSprite into image_processing.py

**Files:**
- Modify: `src/image_processing.py:21-24`

- [ ] **Step 1: Update rotate() to support RotSprite algorithm and pivot**

Replace the existing `rotate` function in `src/image_processing.py:21-24`:

```python
def rotate(grid: PixelGrid, degrees: int, algorithm: str = "rotsprite",
           pivot: tuple[int, int] | None = None) -> PixelGrid:
    """Rotate pixel grid using specified algorithm.

    Args:
        algorithm: "rotsprite" for pixel-art-aware, "fast" for nearest-neighbor
        pivot: rotation center (x, y). Defaults to image center.
    """
    from src.rotsprite import rotsprite_rotate, fast_rotate
    pixels = grid._pixels
    if algorithm == "rotsprite":
        rotated = rotsprite_rotate(pixels, degrees, pivot=pivot)
    else:
        rotated = fast_rotate(pixels, degrees, pivot=pivot)
    result = PixelGrid(grid.width, grid.height)
    result._pixels = rotated
    return result
```

- [ ] **Step 2: Run existing tests to verify no regressions**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All existing tests still PASS

- [ ] **Step 3: Commit**

```bash
git add src/image_processing.py
git commit -m "feat: wire RotSprite algorithm into image_processing.rotate()"
```

---

### Task 3: Canvas Rotation Handles and Interactive Mode

**Files:**
- Modify: `src/canvas.py` — add rotation handle overlay rendering
- Modify: `src/app.py` — add rotation tool mode (Ctrl+T activation, handle drag, bake/cancel)
- Modify: `src/keybindings.py` — register Ctrl+T shortcut

This task is UI-heavy and involves:
1. Drawing rotation handles (corner circles + pivot dot) as canvas overlays
2. Mouse event handling: detect handle hover, drag to rotate, Shift-snap to 15°
3. Live preview: apply fast_rotate during drag, show result
4. Context bar: angle input field, algorithm dropdown (RotSprite/Fast), pivot X/Y
5. Enter to bake (save undo state, apply rotation), Escape to cancel
6. For large selections: Fast preview during drag, RotSprite computed on mouse release

- [ ] **Step 1: Add rotation overlay rendering to canvas.py**

Add a method to `PixelCanvas` that draws rotation handles given a bounding rect and angle. Uses `canvas.create_oval()` for corner handles and pivot dot, `canvas.create_line()` for the bounding box.

- [ ] **Step 2: Add rotation mode state to app.py**

Add to `RetroSpriteApp.__init__()`:
```python
self._rotation_mode = False
self._rotation_angle = 0.0
self._rotation_pivot = None
self._rotation_algorithm = "rotsprite"
self._rotation_original = None  # saved pixels for cancel/undo
self._rotation_bounds = None    # (x, y, w, h) selection bounds
```

- [ ] **Step 3: Add _enter_rotation_mode() and _exit_rotation_mode() to app.py**

`_enter_rotation_mode()`: Save undo state, capture selection/layer pixels, show handles.
`_exit_rotation_mode(apply=False)`: If apply, bake rotated pixels. If cancel, restore original.

- [ ] **Step 4: Add mouse handlers for rotation drag**

In app.py, when `_rotation_mode` is True:
- Mouse down on corner handle: start rotation drag
- Mouse move: compute angle from pivot, Shift-snap to 15°, update preview with fast_rotate
- Mouse up: if algorithm is RotSprite, recompute with rotsprite_rotate
- Mouse down on pivot: start pivot drag
- Enter key: call `_exit_rotation_mode(apply=True)`
- Escape key: call `_exit_rotation_mode(apply=False)`

- [ ] **Step 5: Add Ctrl+T keybinding**

In `src/keybindings.py`, register `"rotate": "<Control-t>"` in default bindings.
In `app.py`, bind it to `_enter_rotation_mode()`.

- [ ] **Step 6: Add context bar for rotation mode**

When rotation mode is active, show in the options/context bar area:
- Angle input field (Spinbox, -360 to 360, step 0.5)
- Algorithm dropdown (RotSprite / Fast)
- Pivot X/Y coordinate fields
- Apply / Cancel buttons

- [ ] **Step 7: Test interactively**

Launch the app, open a sprite, select content, press Ctrl+T, drag corner handle, verify preview updates, Enter to apply, Ctrl+Z to undo.

- [ ] **Step 8: Commit**

```bash
git add src/canvas.py src/app.py src/keybindings.py
git commit -m "feat: add interactive rotation mode with on-canvas handles and RotSprite"
```

---

## Chunk 2: Non-Destructive Layer Effects

### Task 4: LayerEffect Data Model + Effect Functions

**Files:**
- Create: `src/effects.py`
- Create: `tests/test_effects.py`
- Modify: `src/layer.py:11-19` — add `effects` field to Layer.__init__
- Modify: `src/layer.py:27-36` — copy effects in Layer.copy()

- [ ] **Step 1: Add effects field to Layer**

In `src/layer.py:19`, add after `self.is_group = False`:
```python
        self.effects: list = []  # list of LayerEffect dicts
```

In `src/layer.py:27-36`, add to `copy()` after `new_layer.is_group = self.is_group`:
```python
        import copy as copy_mod
        new_layer.effects = copy_mod.deepcopy(self.effects)
```

- [ ] **Step 2: Write failing tests for LayerEffect and core effects**

```python
# tests/test_effects.py
import numpy as np
from src.effects import (
    LayerEffect, apply_effects,
    apply_outline, apply_drop_shadow, apply_inner_shadow,
    apply_hue_sat, apply_gradient_map, apply_glow, apply_pattern_overlay,
)


def _make_square(size=16, color=(255, 0, 0, 255)):
    """Helper: create a square of solid color centered in a transparent canvas."""
    pixels = np.zeros((size, size, 4), dtype=np.uint8)
    q = size // 4
    pixels[q:size-q, q:size-q] = color
    return pixels


class TestLayerEffect:
    def test_create_effect(self):
        fx = LayerEffect("outline", True, {"color": (0, 0, 0, 255), "thickness": 1,
                                            "mode": "outer", "connectivity": 4})
        assert fx.type == "outline"
        assert fx.enabled is True
        assert fx.params["thickness"] == 1

    def test_disabled_effect_skipped(self):
        pixels = _make_square()
        fx = LayerEffect("outline", False, {"color": (0, 0, 0, 255), "thickness": 1,
                                             "mode": "outer", "connectivity": 4})
        result = apply_effects(pixels, [fx])
        assert np.array_equal(result, pixels)


class TestOutline:
    def test_outer_outline_adds_pixels(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        result = apply_outline(pixels, color=(0, 0, 0, 255), thickness=1,
                               mode="outer", connectivity=4)
        # Outline should add black pixels around the red square
        orig_opaque = np.sum(pixels[:, :, 3] > 0)
        result_opaque = np.sum(result[:, :, 3] > 0)
        assert result_opaque > orig_opaque

    def test_inner_outline_doesnt_expand(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        result = apply_outline(pixels, color=(0, 0, 0, 255), thickness=1,
                               mode="inner", connectivity=4)
        orig_opaque = np.sum(pixels[:, :, 3] > 0)
        result_opaque = np.sum(result[:, :, 3] > 0)
        assert result_opaque == orig_opaque

    def test_8_connectivity_more_pixels(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        result4 = apply_outline(pixels, (0, 0, 0, 255), 1, "outer", 4)
        result8 = apply_outline(pixels, (0, 0, 0, 255), 1, "outer", 8)
        count4 = np.sum(result4[:, :, 3] > 0)
        count8 = np.sum(result8[:, :, 3] > 0)
        assert count8 >= count4


class TestDropShadow:
    def test_shadow_adds_pixels_behind(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        result = apply_drop_shadow(pixels, color=(0, 0, 0, 255),
                                   offset_x=2, offset_y=2, blur=0, opacity=1.0)
        orig_opaque = np.sum(pixels[:, :, 3] > 0)
        result_opaque = np.sum(result[:, :, 3] > 0)
        assert result_opaque > orig_opaque

    def test_zero_offset_no_visible_shadow(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        result = apply_drop_shadow(pixels, (0, 0, 0, 255), 0, 0, 0, 1.0)
        # Shadow directly behind sprite — no new visible area
        orig_opaque = np.sum(pixels[:, :, 3] > 0)
        result_opaque = np.sum(result[:, :, 3] > 0)
        assert result_opaque == orig_opaque


class TestInnerShadow:
    def test_inner_shadow_doesnt_expand(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        result = apply_inner_shadow(pixels, (0, 0, 0, 255), 1, 1, 0, 0.5)
        orig_opaque = np.sum(pixels[:, :, 3] > 0)
        result_opaque = np.sum(result[:, :, 3] > 0)
        assert result_opaque == orig_opaque


class TestHueSat:
    def test_zero_shift_near_identity(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        result = apply_hue_sat(pixels, hue=0, saturation=1.0, value=0)
        # Allow ±1 for float round-trip through HSV
        np.testing.assert_allclose(result.astype(float), pixels.astype(float), atol=1)

    def test_hue_shift_changes_color(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        result = apply_hue_sat(pixels, hue=120, saturation=1.0, value=0)
        # Red shifted 120° should be approximately green
        opaque = result[:, :, 3] > 0
        assert np.mean(result[opaque, 1]) > np.mean(result[opaque, 0])


class TestGradientMap:
    def test_two_stop_gradient(self):
        pixels = _make_square(16, (128, 128, 128, 255))
        stops = [(0.0, (0, 0, 0, 255)), (1.0, (255, 255, 255, 255))]
        result = apply_gradient_map(pixels, stops=stops, opacity=1.0)
        opaque = result[:, :, 3] > 0
        # Gray should map to mid-range
        avg = np.mean(result[opaque, 0])
        assert 100 < avg < 200


class TestGlow:
    def test_glow_adds_brightness(self):
        pixels = _make_square(16, (255, 255, 255, 255))
        result = apply_glow(pixels, threshold=200, radius=2, intensity=1.0,
                            tint=(255, 255, 255, 255))
        # Glow should spread bright pixels beyond original bounds
        orig_bright = np.sum(pixels[:, :, 3] > 0)
        result_bright = np.sum(result[:, :, 3] > 0)
        assert result_bright >= orig_bright


class TestPatternOverlay:
    def test_pattern_clipped_to_alpha(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        result = apply_pattern_overlay(pixels, pattern="checkerboard",
                                       blend_mode="multiply", opacity=0.5,
                                       scale=1, offset_x=0, offset_y=0)
        # Transparent areas should remain transparent
        orig_transparent = pixels[:, :, 3] == 0
        assert np.all(result[orig_transparent, 3] == 0)


class TestApplyEffects:
    def test_multiple_effects_applied_in_order(self):
        pixels = _make_square(16, (255, 0, 0, 255))
        effects = [
            LayerEffect("outline", True, {"color": (0, 0, 0, 255), "thickness": 1,
                                           "mode": "outer", "connectivity": 4}),
            LayerEffect("drop_shadow", True, {"color": (0, 0, 0, 255),
                                               "offset_x": 2, "offset_y": 2,
                                               "blur": 0, "opacity": 0.7}),
        ]
        result = apply_effects(pixels, effects)
        orig_opaque = np.sum(pixels[:, :, 3] > 0)
        result_opaque = np.sum(result[:, :, 3] > 0)
        assert result_opaque > orig_opaque
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_effects.py -v`
Expected: FAIL with ImportError

- [ ] **Step 4: Implement effects.py with all 7 effects**

```python
# src/effects.py
"""Non-destructive layer effects for RetroSprite."""
from __future__ import annotations
import numpy as np
from PIL import Image, ImageFilter
from src.layer import apply_blend_mode


class LayerEffect:
    """A non-destructive effect applied to a layer during compositing."""

    def __init__(self, type: str, enabled: bool, params: dict):
        self.type = type
        self.enabled = enabled
        self.params = params

    def to_dict(self) -> dict:
        return {"type": self.type, "enabled": self.enabled, "params": self.params}

    @classmethod
    def from_dict(cls, data: dict) -> LayerEffect:
        return cls(data["type"], data["enabled"], data["params"])


def _shift_array(arr: np.ndarray, dx: int, dy: int) -> np.ndarray:
    """Shift a 2D RGBA array by (dx, dy), filling exposed edges with zeros."""
    result = np.zeros_like(arr)
    h, w = arr.shape[:2]
    # Compute source and dest slices
    sx_start = max(0, -dx)
    sx_end = min(w, w - dx)
    sy_start = max(0, -dy)
    sy_end = min(h, h - dy)
    dx_start = max(0, dx)
    dx_end = min(w, w + dx)
    dy_start = max(0, dy)
    dy_end = min(h, h + dy)
    if sx_end > sx_start and sy_end > sy_start:
        result[dy_start:dy_end, dx_start:dx_end] = arr[sy_start:sy_end, sx_start:sx_end]
    return result


def _gaussian_blur_rgba(pixels: np.ndarray, radius: int) -> np.ndarray:
    """Apply Gaussian blur to an RGBA array, preserving alpha correctly."""
    if radius <= 0:
        return pixels.copy()
    img = Image.fromarray(pixels, "RGBA")
    blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
    return np.array(blurred, dtype=np.uint8)


def _alpha_composite(below: np.ndarray, above: np.ndarray) -> np.ndarray:
    """Composite 'above' onto 'below' using standard alpha blending."""
    below_img = Image.fromarray(below, "RGBA")
    above_img = Image.fromarray(above, "RGBA")
    return np.array(Image.alpha_composite(below_img, above_img), dtype=np.uint8)


# ---------- CORE EFFECTS ----------

def apply_outline(pixels: np.ndarray, color: tuple, thickness: int,
                  mode: str, connectivity: int,
                  original_alpha: np.ndarray | None = None) -> np.ndarray:
    """Add outline around opaque pixels. Uses original_alpha if provided."""
    result = pixels.copy()
    h, w = pixels.shape[:2]
    alpha = original_alpha if original_alpha is not None else pixels[:, :, 3]

    if connectivity == 8:
        struct_offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                         (0, 1), (1, -1), (1, 0), (1, 1)]
    else:
        struct_offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    for _ in range(thickness):
        current_alpha = result[:, :, 3]
        opaque = current_alpha > 0

        if mode in ("outer", "both"):
            # Dilate: find transparent pixels adjacent to opaque
            dilated = np.zeros_like(opaque)
            for dy, dx in struct_offsets:
                shifted = np.roll(np.roll(opaque, dy, axis=0), dx, axis=1)
                # Zero out wrapped edges
                if dy < 0:
                    shifted[-1:, :] = False
                elif dy > 0:
                    shifted[:1, :] = False
                if dx < 0:
                    shifted[:, -1:] = False
                elif dx > 0:
                    shifted[:, :1] = False
                dilated |= shifted
            outline_mask = dilated & ~opaque
            result[outline_mask] = list(color)

        if mode in ("inner", "both"):
            # Erode: find opaque pixels adjacent to transparent
            eroded = np.ones_like(opaque)
            for dy, dx in struct_offsets:
                shifted = np.roll(np.roll(opaque, dy, axis=0), dx, axis=1)
                if dy < 0:
                    shifted[-1:, :] = False
                elif dy > 0:
                    shifted[:1, :] = False
                if dx < 0:
                    shifted[:, -1:] = False
                elif dx > 0:
                    shifted[:, :1] = False
                eroded &= shifted
            inner_mask = opaque & ~eroded
            result[inner_mask] = list(color)

    return result


def apply_drop_shadow(pixels: np.ndarray, color: tuple, offset_x: int,
                      offset_y: int, blur: int, opacity: float,
                      original_alpha: np.ndarray | None = None) -> np.ndarray:
    """Add drop shadow behind the layer. Uses original_alpha for shadow shape."""
    h, w = pixels.shape[:2]
    shadow = np.zeros((h, w, 4), dtype=np.uint8)
    alpha = original_alpha if original_alpha is not None else pixels[:, :, 3]
    shadow_mask = alpha > 0
    shadow_color = list(color[:3]) + [int(255 * opacity)]
    shadow[shadow_mask] = shadow_color
    shadow = _shift_array(shadow, offset_x, offset_y)
    if blur > 0:
        shadow = _gaussian_blur_rgba(shadow, blur)
    return _alpha_composite(shadow, pixels)


def apply_inner_shadow(pixels: np.ndarray, color: tuple, offset_x: int,
                       offset_y: int, blur: int, opacity: float,
                       original_alpha: np.ndarray | None = None) -> np.ndarray:
    """Add inner shadow inside opaque areas. Uses original_alpha if provided."""
    h, w = pixels.shape[:2]
    orig_alpha = original_alpha if original_alpha is not None else pixels[:, :, 3]

    # Create inverted mask shadow
    inv_mask = orig_alpha == 0
    shadow = np.zeros((h, w, 4), dtype=np.uint8)
    shadow_color = list(color[:3]) + [int(255 * opacity)]
    shadow[inv_mask] = shadow_color
    shadow = _shift_array(shadow, offset_x, offset_y)
    if blur > 0:
        shadow = _gaussian_blur_rgba(shadow, blur)

    # Clip to original alpha
    shadow[orig_alpha == 0] = [0, 0, 0, 0]

    return _alpha_composite(pixels, shadow)


# ---------- COLOR EFFECTS ----------

def apply_hue_sat(pixels: np.ndarray, hue: int, saturation: float,
                  value: int) -> np.ndarray:
    """Shift hue, scale saturation, offset value. Vectorized RGB->HSV->RGB."""
    result = pixels.copy()
    opaque = pixels[:, :, 3] > 0
    if not np.any(opaque):
        return result

    # Vectorized RGB->HSV using NumPy (no per-pixel Python loop)
    rgb = pixels[:, :, :3].astype(np.float32) / 255.0
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin

    # Hue
    h_arr = np.zeros_like(cmax)
    mask_r = (cmax == r) & (delta > 0)
    mask_g = (cmax == g) & (delta > 0) & ~mask_r
    mask_b = (cmax == b) & (delta > 0) & ~mask_r & ~mask_g
    h_arr[mask_r] = (((g[mask_r] - b[mask_r]) / delta[mask_r]) % 6) / 6.0
    h_arr[mask_g] = (((b[mask_g] - r[mask_g]) / delta[mask_g]) + 2) / 6.0
    h_arr[mask_b] = (((r[mask_b] - g[mask_b]) / delta[mask_b]) + 4) / 6.0

    # Saturation
    s_arr = np.where(cmax > 0, delta / cmax, 0.0)
    # Value
    v_arr = cmax

    # Apply shifts
    h_arr = (h_arr + hue / 360.0) % 1.0
    s_arr = np.clip(s_arr * saturation, 0.0, 1.0)
    v_arr = np.clip(v_arr + value / 255.0, 0.0, 1.0)

    # Vectorized HSV->RGB
    h6 = h_arr * 6.0
    i = h6.astype(np.int32) % 6
    f = h6 - np.floor(h6)
    p = v_arr * (1 - s_arr)
    q = v_arr * (1 - f * s_arr)
    t = v_arr * (1 - (1 - f) * s_arr)

    nr = np.where(i == 0, v_arr, np.where(i == 1, q, np.where(i == 2, p,
         np.where(i == 3, p, np.where(i == 4, t, v_arr)))))
    ng = np.where(i == 0, t, np.where(i == 1, v_arr, np.where(i == 2, v_arr,
         np.where(i == 3, q, np.where(i == 4, p, p)))))
    nb = np.where(i == 0, p, np.where(i == 1, p, np.where(i == 2, t,
         np.where(i == 3, v_arr, np.where(i == 4, v_arr, q)))))

    result[opaque, 0] = (nr[opaque] * 255).astype(np.uint8)
    result[opaque, 1] = (ng[opaque] * 255).astype(np.uint8)
    result[opaque, 2] = (nb[opaque] * 255).astype(np.uint8)

    return result


def apply_gradient_map(pixels: np.ndarray, stops: list,
                       opacity: float) -> np.ndarray:
    """Map luminance to color gradient."""
    result = pixels.copy()
    # Compute luminance
    lum = (0.299 * pixels[:, :, 0].astype(np.float32) +
           0.587 * pixels[:, :, 1].astype(np.float32) +
           0.114 * pixels[:, :, 2].astype(np.float32)) / 255.0

    opaque = pixels[:, :, 3] > 0

    # Sort stops by position
    stops = sorted(stops, key=lambda s: s[0])

    # Build lookup table (256 entries)
    lut = np.zeros((256, 4), dtype=np.uint8)
    for i in range(256):
        t = i / 255.0
        # Find surrounding stops
        below = stops[0]
        above = stops[-1]
        for j in range(len(stops) - 1):
            if stops[j][0] <= t <= stops[j + 1][0]:
                below = stops[j]
                above = stops[j + 1]
                break
        # Interpolate
        span = above[0] - below[0]
        if span > 0:
            frac = (t - below[0]) / span
        else:
            frac = 0.0
        for c in range(4):
            lut[i, c] = int(below[1][c] + frac * (above[1][c] - below[1][c]))

    # Apply LUT
    lum_idx = (lum * 255).astype(np.uint8)
    mapped = lut[lum_idx]

    # Blend mapped with original at opacity
    if opacity < 1.0:
        blend = opacity
        result[opaque, :3] = (mapped[opaque, :3].astype(np.float32) * blend +
                               pixels[opaque, :3].astype(np.float32) * (1 - blend)).astype(np.uint8)
    else:
        result[opaque, :3] = mapped[opaque, :3]

    return result


# ---------- ADVANCED EFFECTS ----------

def apply_glow(pixels: np.ndarray, threshold: int, radius: int,
               intensity: float, tint: tuple) -> np.ndarray:
    """Add glow/bloom to bright areas."""
    # Extract bright pixels
    lum = (0.299 * pixels[:, :, 0].astype(np.float32) +
           0.587 * pixels[:, :, 1].astype(np.float32) +
           0.114 * pixels[:, :, 2].astype(np.float32))
    bright_mask = (lum > threshold) & (pixels[:, :, 3] > 0)

    bright = np.zeros_like(pixels)
    bright[bright_mask] = pixels[bright_mask]

    # Tint
    if tint != (255, 255, 255, 255):
        tint_arr = np.array(tint[:3], dtype=np.float32) / 255.0
        bright[bright_mask, 0] = (bright[bright_mask, 0] * tint_arr[0]).astype(np.uint8)
        bright[bright_mask, 1] = (bright[bright_mask, 1] * tint_arr[1]).astype(np.uint8)
        bright[bright_mask, 2] = (bright[bright_mask, 2] * tint_arr[2]).astype(np.uint8)

    # Blur
    blurred = _gaussian_blur_rgba(bright, radius)

    # Intensity
    if intensity != 1.0:
        blurred[:, :, :3] = np.clip(
            blurred[:, :, :3].astype(np.float32) * intensity, 0, 255
        ).astype(np.uint8)

    # Screen blend onto original
    result = pixels.copy()
    blend_arr = np.array(result, dtype=np.uint8)
    screen = apply_blend_mode(blend_arr, blurred, "screen")
    # Only apply where blurred has alpha
    glow_alpha = blurred[:, :, 3].astype(np.float32) / 255.0
    for c in range(3):
        result[:, :, c] = (
            result[:, :, c] * (1 - glow_alpha) +
            screen[:, :, c] * glow_alpha
        ).astype(np.uint8)
    result[:, :, 3] = np.maximum(result[:, :, 3], blurred[:, :, 3])

    return result


# Built-in patterns
PATTERNS = {
    "scanlines": np.array([[255, 255, 255, 255], [0, 0, 0, 255],
                            [255, 255, 255, 255], [0, 0, 0, 255]], dtype=np.uint8
                           ).reshape(4, 1, 4).repeat(4, axis=1),
    "checkerboard": None,  # generated dynamically
    "dots": None,
    "crosshatch": None,
    "diagonal": None,
    "noise": None,
}


def _generate_pattern(name: str, size: int = 4) -> np.ndarray:
    """Generate a built-in pattern as (size, size, 4) uint8 array."""
    p = np.zeros((size, size, 4), dtype=np.uint8)
    if name == "scanlines":
        for y in range(size):
            val = 255 if y % 2 == 0 else 0
            p[y, :] = [val, val, val, 255]
    elif name == "checkerboard":
        for y in range(size):
            for x in range(size):
                val = 255 if (x + y) % 2 == 0 else 0
                p[y, x] = [val, val, val, 255]
    elif name == "dots":
        p[:, :] = [0, 0, 0, 255]
        p[0, 0] = [255, 255, 255, 255]
    elif name == "crosshatch":
        for y in range(size):
            for x in range(size):
                if y % 2 == 0 or x % 2 == 0:
                    p[y, x] = [255, 255, 255, 255]
                else:
                    p[y, x] = [0, 0, 0, 255]
    elif name == "diagonal":
        for y in range(size):
            for x in range(size):
                val = 255 if (x + y) % 3 == 0 else 0
                p[y, x] = [val, val, val, 255]
    elif name == "noise":
        rng = np.random.RandomState(42)  # deterministic
        vals = rng.randint(0, 256, (size, size), dtype=np.uint8)
        p[:, :, 0] = vals
        p[:, :, 1] = vals
        p[:, :, 2] = vals
        p[:, :, 3] = 255
    return p


def apply_pattern_overlay(pixels: np.ndarray, pattern: str, blend_mode: str,
                          opacity: float, scale: int, offset_x: int,
                          offset_y: int) -> np.ndarray:
    """Tile a pattern across the layer, blend, and clip to alpha."""
    h, w = pixels.shape[:2]
    pat = _generate_pattern(pattern, 4 * scale)
    ph, pw = pat.shape[:2]

    # Tile pattern across layer (vectorized)
    ys = (np.arange(h)[:, None] + offset_y) % ph
    xs = (np.arange(w)[None, :] + offset_x) % pw
    tiled = pat[ys, xs]

    # Clip to layer alpha
    tiled[pixels[:, :, 3] == 0] = [0, 0, 0, 0]

    # Apply opacity
    tiled[:, :, 3] = (tiled[:, :, 3].astype(np.float32) * opacity).astype(np.uint8)

    # Blend onto pixels
    if blend_mode == "normal":
        return _alpha_composite(pixels, tiled)
    else:
        blended = apply_blend_mode(pixels, tiled, blend_mode)
        pat_alpha = tiled[:, :, 3].astype(np.float32) / 255.0
        result = pixels.copy()
        for c in range(3):
            result[:, :, c] = (
                pixels[:, :, c] * (1 - pat_alpha) +
                blended[:, :, c] * pat_alpha
            ).astype(np.uint8)
        return result


# ---------- MASTER PIPELINE ----------

EFFECT_FUNCS = {
    "outline": lambda p, **kw: apply_outline(p, **kw),
    "drop_shadow": lambda p, **kw: apply_drop_shadow(p, **kw),
    "inner_shadow": lambda p, **kw: apply_inner_shadow(p, **kw),
    "hue_sat": lambda p, **kw: apply_hue_sat(p, **kw),
    "gradient_map": lambda p, **kw: apply_gradient_map(p, **kw),
    "glow": lambda p, **kw: apply_glow(p, **kw),
    "pattern_overlay": lambda p, **kw: apply_pattern_overlay(p, **kw),
}

# Ordered by application sequence (spec-defined)
EFFECT_ORDER = ["hue_sat", "gradient_map", "pattern_overlay", "glow",
                "inner_shadow", "outline", "drop_shadow"]


def apply_effects(pixels: np.ndarray, effects: list,
                  original_alpha: np.ndarray | None = None) -> np.ndarray:
    """Apply all enabled effects in spec-defined order.

    Args:
        pixels: (H,W,4) uint8 source pixels (will be copied, not modified).
        effects: list of LayerEffect objects.
        original_alpha: saved alpha mask for outline/shadow computation.
                        If None, uses pixels[:,:,3].
    """
    if not effects:
        return pixels

    result = pixels.copy()
    if original_alpha is None:
        original_alpha = pixels[:, :, 3].copy()

    # Sort effects by spec order, preserving user order within same type
    enabled = [fx for fx in effects if fx.enabled]
    if not enabled:
        return result

    # Group by type for ordered application
    by_type = {}
    for fx in enabled:
        by_type.setdefault(fx.type, []).append(fx)

    for effect_type in EFFECT_ORDER:
        if effect_type not in by_type:
            continue
        for fx in by_type[effect_type]:
            func = EFFECT_FUNCS.get(fx.type)
            if func:
                # Spatial effects use original alpha mask, not modified pixels
                if fx.type in ("outline", "drop_shadow", "inner_shadow"):
                    result = func(result, original_alpha=original_alpha, **fx.params)
                else:
                    result = func(result, **fx.params)

    return result
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_effects.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/effects.py tests/test_effects.py src/layer.py
git commit -m "feat: add non-destructive layer effects engine with 7 effects"
```

---

### Task 5: Integrate Effects into Rendering Pipeline

**Files:**
- Modify: `src/layer.py:141` — add effect application in flatten_layers()

- [ ] **Step 1: Add effect application to flatten_layers()**

In `src/layer.py`, at line 141 (where `layer_img = layer.pixels.to_pil_image()`), wrap with effect processing:

```python
        # Before: layer_img = layer.pixels.to_pil_image()
        # After:
        layer_pixels = layer.pixels
        if hasattr(layer, 'effects') and layer.effects:
            from src.effects import apply_effects
            raw = layer_pixels._pixels.copy()
            original_alpha = raw[:, :, 3].copy()
            processed = apply_effects(raw, layer.effects, original_alpha)
            from PIL import Image
            layer_img = Image.fromarray(processed, "RGBA")
        else:
            layer_img = layer_pixels.to_pil_image()
```

- [ ] **Step 2: Run all tests to verify no regressions**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All PASS (250+ existing + new effect tests)

- [ ] **Step 3: Commit**

```bash
git add src/layer.py
git commit -m "feat: integrate layer effects into flatten_layers() rendering pipeline"
```

---

### Task 6: Effects Dialog UI

**Files:**
- Create: `src/ui/effects_dialog.py`
- Modify: `src/ui/timeline.py` — add FX button per layer row
- Modify: `src/app.py` — wire FX button callback

- [ ] **Step 1: Create effects_dialog.py**

A Tkinter Toplevel dialog with:
- Left panel: Listbox of active effects with checkboxes, Add/Remove/Up/Down buttons
- Right panel: parameter controls for selected effect (varies by type)
- Apply/Cancel buttons at bottom
- Live preview callback: calls `app._render_canvas()` on every param change

Key implementation details:
- Each effect type has a param builder method that creates appropriate widgets (Spinbox for numbers, OptionMenu for choices, color button for colors)
- Color picker button opens `tkinter.colorchooser.askcolor()`
- Effects list backed by the layer's `effects` list (deep-copied on open, applied on Apply)

- [ ] **Step 2: Add FX button to timeline layer rows**

In `src/ui/timeline.py`, in the layer sidebar rendering method, add a small "FX" button per layer row:
- Button text: "FX"
- Background: magenta-tinted when `layer.effects` is non-empty, dim otherwise
- Click callback: opens `EffectsDialog` for that layer

- [ ] **Step 3: Wire in app.py**

Add callback `_on_layer_fx_click(layer_index)` that opens `EffectsDialog` passing the layer and a render callback.

- [ ] **Step 4: Add View > Display Layer Effects toggle**

In app.py menu setup, add a toggle under View menu. Store as `self._display_effects = True`. When False, temporarily clear `layer.effects` before calling `flatten_layers()` in `_render_canvas()` and restore after. This avoids threading flags into `flatten_layers()`:

```python
def _render_canvas(self):
    if not self._display_effects:
        # Temporarily hide effects for preview
        saved = []
        frame = self.timeline.current_frame_obj()
        for layer in frame.layers:
            saved.append(layer.effects)
            layer.effects = []
    # ... existing render code ...
    if not self._display_effects:
        for layer, fx in zip(frame.layers, saved):
            layer.effects = fx
```

Effects are always applied on export (export code does NOT check this flag).

- [ ] **Step 5: Test interactively**

Launch app, create sprite, click FX button, add Outline effect, verify preview updates live, click Apply, verify effect persists on canvas.

- [ ] **Step 6: Commit**

```bash
git add src/ui/effects_dialog.py src/ui/timeline.py src/app.py
git commit -m "feat: add FX button and effects config dialog with live preview"
```

---

### Task 7: Serialize Effects in Project v3

**Files:**
- Modify: `src/project.py:17-27` — save effects in layer data
- Modify: `src/project.py:69-81` — load effects from layer data

- [ ] **Step 1: Add effects to save_project()**

In `src/project.py`, in the layer serialization block (line 18-27), add after `"is_group"`:

```python
                "effects": [fx.to_dict() for fx in getattr(layer, 'effects', [])],
```

Change version from 2 to 3:
```python
        "version": 3,
```

- [ ] **Step 2: Add effects to load_project()**

In `src/project.py`, in the layer loading block (line 69-81), add after `layer.is_group = ...`:

```python
                from src.effects import LayerEffect
                layer.effects = [LayerEffect.from_dict(e) for e in layer_data.get("effects", [])]
```

- [ ] **Step 3: Run all tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/project.py
git commit -m "feat: serialize layer effects in project v3 format"
```

---

## Chunk 3: Tilemap Layers

### Task 8: Tileset and TileRef Data Model

**Files:**
- Create: `src/tilemap.py`
- Create: `tests/test_tilemap.py`

- [ ] **Step 1: Write failing tests for Tileset and TileRef**

```python
# tests/test_tilemap.py
import numpy as np
from src.tilemap import Tileset, TileRef, TilemapLayer
from src.layer import Layer


class TestTileRef:
    def test_create_empty(self):
        ref = TileRef(0)
        assert ref.index == 0
        assert ref.flip_x is False
        assert ref.flip_y is False

    def test_create_with_flips(self):
        ref = TileRef(5, flip_x=True, flip_y=True)
        assert ref.index == 5
        assert ref.flip_x is True

    def test_pack_unpack(self):
        ref = TileRef(42, flip_x=True, flip_y=False)
        packed = ref.pack()
        unpacked = TileRef.unpack(packed)
        assert unpacked.index == 42
        assert unpacked.flip_x is True
        assert unpacked.flip_y is False


class TestTileset:
    def test_create_tileset(self):
        ts = Tileset("Test", 16, 16)
        assert ts.name == "Test"
        assert ts.tile_width == 16
        assert len(ts.tiles) == 1  # empty tile at index 0

    def test_add_tile(self):
        ts = Tileset("Test", 8, 8)
        tile = np.full((8, 8, 4), [255, 0, 0, 255], dtype=np.uint8)
        idx = ts.add_tile(tile)
        assert idx == 1
        assert len(ts.tiles) == 2
        assert np.array_equal(ts.tiles[1], tile)

    def test_empty_tile_is_transparent(self):
        ts = Tileset("Test", 8, 8)
        assert np.all(ts.tiles[0][:, :, 3] == 0)

    def test_find_matching(self):
        ts = Tileset("Test", 8, 8)
        tile = np.full((8, 8, 4), [0, 255, 0, 255], dtype=np.uint8)
        ts.add_tile(tile)
        found = ts.find_matching(tile)
        assert found == 1

    def test_find_matching_not_found(self):
        ts = Tileset("Test", 8, 8)
        tile = np.full((8, 8, 4), [0, 0, 255, 255], dtype=np.uint8)
        assert ts.find_matching(tile) is None

    def test_update_tile(self):
        ts = Tileset("Test", 8, 8)
        tile = np.full((8, 8, 4), [255, 0, 0, 255], dtype=np.uint8)
        idx = ts.add_tile(tile)
        new_tile = np.full((8, 8, 4), [0, 255, 0, 255], dtype=np.uint8)
        ts.update_tile(idx, new_tile)
        assert np.array_equal(ts.tiles[idx], new_tile)

    def test_remove_tile(self):
        ts = Tileset("Test", 8, 8)
        ts.add_tile(np.full((8, 8, 4), [255, 0, 0, 255], dtype=np.uint8))
        ts.add_tile(np.full((8, 8, 4), [0, 255, 0, 255], dtype=np.uint8))
        assert len(ts.tiles) == 3
        ts.remove_tile(1)
        assert len(ts.tiles) == 2

    def test_import_from_image(self):
        from PIL import Image
        # Create a 16x8 image with two 8x8 tiles
        img = Image.new("RGBA", (16, 8), (0, 0, 0, 0))
        for x in range(8):
            for y in range(8):
                img.putpixel((x, y), (255, 0, 0, 255))
        for x in range(8, 16):
            for y in range(8):
                img.putpixel((x, y), (0, 255, 0, 255))
        import tempfile, os
        path = os.path.join(tempfile.gettempdir(), "test_tileset.png")
        img.save(path)
        ts = Tileset.import_from_image(path, 8, 8)
        os.unlink(path)
        assert len(ts.tiles) >= 3  # empty + 2 tiles
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tilemap.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement Tileset and TileRef**

```python
# src/tilemap.py
"""Tilemap layer support for RetroSprite."""
from __future__ import annotations
import numpy as np
from PIL import Image
from src.pixel_data import PixelGrid
from src.layer import Layer


class TileRef:
    """Reference to a tile in a tileset, with flip transforms."""

    def __init__(self, index: int = 0, flip_x: bool = False, flip_y: bool = False):
        self.index = index
        self.flip_x = flip_x
        self.flip_y = flip_y

    def pack(self) -> int:
        """Pack into uint32: [flip_y:1][flip_x:1][unused:14][index:16]."""
        val = self.index & 0xFFFF
        if self.flip_x:
            val |= (1 << 30)
        if self.flip_y:
            val |= (1 << 31)
        return val

    @classmethod
    def unpack(cls, packed: int) -> TileRef:
        index = packed & 0xFFFF
        flip_x = bool(packed & (1 << 30))
        flip_y = bool(packed & (1 << 31))
        return cls(index, flip_x, flip_y)

    def copy(self) -> TileRef:
        return TileRef(self.index, self.flip_x, self.flip_y)


class Tileset:
    """A collection of same-size tile images."""

    def __init__(self, name: str, tile_width: int, tile_height: int):
        self.name = name
        self.tile_width = tile_width
        self.tile_height = tile_height
        # Index 0 is always the empty/transparent tile
        self.tiles: list[np.ndarray] = [
            np.zeros((tile_height, tile_width, 4), dtype=np.uint8)
        ]

    def add_tile(self, pixels: np.ndarray) -> int:
        """Add a tile and return its index."""
        self.tiles.append(pixels.copy())
        return len(self.tiles) - 1

    def remove_tile(self, index: int) -> None:
        """Remove tile at index (cannot remove index 0)."""
        if index > 0 and index < len(self.tiles):
            self.tiles.pop(index)

    def update_tile(self, index: int, pixels: np.ndarray) -> None:
        """Update tile content at index."""
        if 0 < index < len(self.tiles):
            self.tiles[index] = pixels.copy()

    def find_matching(self, pixels: np.ndarray) -> int | None:
        """Find a tile with identical pixels. Returns index or None."""
        for i, tile in enumerate(self.tiles):
            if i == 0:
                continue
            if np.array_equal(tile, pixels):
                return i
        return None

    @classmethod
    def import_from_image(cls, image_path: str, tile_w: int, tile_h: int,
                          name: str = "Imported") -> Tileset:
        """Import a tileset image and auto-slice into tiles with dedup."""
        img = Image.open(image_path).convert("RGBA")
        tileset = cls(name, tile_w, tile_h)

        for y in range(0, img.height, tile_h):
            for x in range(0, img.width, tile_w):
                if x + tile_w > img.width or y + tile_h > img.height:
                    continue
                tile = np.array(img.crop((x, y, x + tile_w, y + tile_h)),
                                dtype=np.uint8)
                if tile[:, :, 3].sum() == 0:
                    continue
                if tileset.find_matching(tile) is None:
                    tileset.add_tile(tile)

        return tileset
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_tilemap.py::TestTileRef tests/test_tilemap.py::TestTileset -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tilemap.py tests/test_tilemap.py
git commit -m "feat: add Tileset and TileRef data model with import/dedup"
```

---

### Task 9: TilemapLayer Class

**Files:**
- Modify: `src/tilemap.py` — add TilemapLayer class
- Add tests: `tests/test_tilemap.py`

- [ ] **Step 1: Write failing tests for TilemapLayer**

Add to `tests/test_tilemap.py`:

```python
class TestTilemapLayer:
    def test_create_tilemap_layer(self):
        ts = Tileset("Test", 8, 8)
        tl = TilemapLayer("Tilemap 1", 32, 32, ts)
        assert tl.grid_cols == 4
        assert tl.grid_rows == 4
        assert tl.is_tilemap()

    def test_all_cells_empty_initially(self):
        ts = Tileset("Test", 8, 8)
        tl = TilemapLayer("Tilemap 1", 16, 16, ts)
        for row in tl.grid:
            for ref in row:
                assert ref.index == 0

    def test_render_empty_is_transparent(self):
        ts = Tileset("Test", 8, 8)
        tl = TilemapLayer("Tilemap 1", 16, 16, ts)
        rendered = tl.render_to_pixels()
        assert rendered.shape == (16, 16, 4)
        assert np.all(rendered[:, :, 3] == 0)

    def test_place_tile_and_render(self):
        ts = Tileset("Test", 8, 8)
        tile = np.full((8, 8, 4), [255, 0, 0, 255], dtype=np.uint8)
        idx = ts.add_tile(tile)
        tl = TilemapLayer("Tilemap 1", 16, 16, ts)
        tl.grid[0][0] = TileRef(idx)
        rendered = tl.render_to_pixels()
        # Top-left 8x8 should be red
        assert np.all(rendered[0:8, 0:8, 0] == 255)
        assert np.all(rendered[0:8, 0:8, 3] == 255)
        # Rest should be transparent
        assert np.all(rendered[8:16, :, 3] == 0)

    def test_flip_x_tile(self):
        ts = Tileset("Test", 4, 4)
        tile = np.zeros((4, 4, 4), dtype=np.uint8)
        tile[:, 0] = [255, 0, 0, 255]  # red left column
        idx = ts.add_tile(tile)
        tl = TilemapLayer("Test", 4, 4, ts)
        tl.grid[0][0] = TileRef(idx, flip_x=True)
        rendered = tl.render_to_pixels()
        # After flip_x, red should be in right column
        assert np.all(rendered[:, 3, 0] == 255)

    def test_copy_preserves_tilemap_data(self):
        ts = Tileset("Test", 8, 8)
        tile = np.full((8, 8, 4), [255, 0, 0, 255], dtype=np.uint8)
        ts.add_tile(tile)
        tl = TilemapLayer("Tilemap 1", 16, 16, ts)
        tl.grid[0][0] = TileRef(1)
        copy = tl.copy()
        assert copy.is_tilemap()
        assert copy.grid[0][0].index == 1
        assert copy.tileset is ts  # shared reference
        # Modifying copy grid shouldn't affect original
        copy.grid[0][0] = TileRef(0)
        assert tl.grid[0][0].index == 1

    def test_pixels_property_returns_pixelgrid(self):
        ts = Tileset("Test", 8, 8)
        tl = TilemapLayer("Tilemap 1", 16, 16, ts)
        pg = tl.pixels
        assert hasattr(pg, 'to_pil_image')
        assert pg.width == 16
        assert pg.height == 16
```

- [ ] **Step 2: Implement TilemapLayer**

Add to `src/tilemap.py`:

```python
class TilemapLayer(Layer):
    """A layer that stores tile references instead of raw pixels."""

    def __init__(self, name: str, width: int, height: int, tileset: Tileset):
        super().__init__(name, width, height)
        self.tileset = tileset
        self.grid_cols = width // tileset.tile_width
        self.grid_rows = height // tileset.tile_height
        self.grid: list[list[TileRef]] = [
            [TileRef(0) for _ in range(self.grid_cols)]
            for _ in range(self.grid_rows)
        ]
        self.edit_mode: str = "pixels"
        self.pixel_sub_mode: str = "auto"

    def is_tilemap(self) -> bool:
        return True

    @property
    def pixels(self) -> PixelGrid:
        """Override to render tile grid as PixelGrid for flatten_layers().
        IMPORTANT: Compute dimensions from grid_cols/grid_rows, never self.pixels (recursion!)."""
        w = self.grid_cols * self.tileset.tile_width
        h = self.grid_rows * self.tileset.tile_height
        pg = PixelGrid(w, h)
        pg._pixels = self.render_to_pixels()
        return pg

    def render_to_pixels(self) -> np.ndarray:
        """Resolve tile grid into a pixel buffer.
        IMPORTANT: Compute dimensions from grid_cols/grid_rows, never self.pixels (recursion!)."""
        tw, th = self.tileset.tile_width, self.tileset.tile_height
        w = self.grid_cols * tw
        h = self.grid_rows * th
        result = np.zeros((h, w, 4), dtype=np.uint8)

        for row in range(self.grid_rows):
            for col in range(self.grid_cols):
                ref = self.grid[row][col]
                if ref.index == 0 or ref.index >= len(self.tileset.tiles):
                    continue
                tile = self.tileset.tiles[ref.index].copy()
                if ref.flip_x:
                    tile = np.flip(tile, axis=1)
                if ref.flip_y:
                    tile = np.flip(tile, axis=0)
                y0 = row * th
                x0 = col * tw
                result[y0:y0+th, x0:x0+tw] = tile

        return result

    def copy(self) -> TilemapLayer:
        """Deep-copy grid, share tileset reference."""
        new = TilemapLayer(f"{self.name} Copy",
                           self.grid_cols * self.tileset.tile_width,
                           self.grid_rows * self.tileset.tile_height,
                           self.tileset)
        new.grid = [[ref.copy() for ref in row] for row in self.grid]
        new.visible = self.visible
        new.opacity = self.opacity
        new.blend_mode = self.blend_mode
        new.locked = self.locked
        new.depth = self.depth
        new.is_group = self.is_group
        new.edit_mode = self.edit_mode
        new.pixel_sub_mode = self.pixel_sub_mode
        import copy as copy_mod
        new.effects = copy_mod.deepcopy(self.effects)
        return new
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_tilemap.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/tilemap.py tests/test_tilemap.py
git commit -m "feat: add TilemapLayer with render_to_pixels, copy, flip transforms"
```

---

### Task 10: Animation Guards for TilemapLayer

**Files:**
- Modify: `src/animation.py:94-114` — sync_layers guard
- Modify: `src/animation.py:135-166` — add_frame/insert_frame guards
- Modify: `src/animation.py:221-230` — merge_down guard

- [ ] **Step 1: Update sync_layers() to handle TilemapLayer**

In `src/animation.py:110`, replace the plain `Layer` creation:

```python
                # Check if reference layer is a tilemap
                if hasattr(ref_layer, 'is_tilemap') and ref_layer.is_tilemap():
                    from src.tilemap import TilemapLayer
                    new_layer = TilemapLayer(ref_layer.name, self.width, self.height,
                                            ref_layer.tileset)
                else:
                    new_layer = Layer(ref_layer.name, self.width, self.height)
```

- [ ] **Step 2: Update add_frame() and insert_frame() similarly**

In `src/animation.py:142` (inside the `while` loop in `add_frame`), the new layer is created via `new_frame.add_layer()` which always creates a plain Layer. Instead, after the loop, replace layers that should be tilemaps:

```python
            for i, ref_layer in enumerate(ref.layers):
                new_frame.layers[i].name = ref_layer.name
                new_frame.layers[i].visible = ref_layer.visible
                new_frame.layers[i].locked = ref_layer.locked
                new_frame.layers[i].opacity = ref_layer.opacity
                # Replace with TilemapLayer if needed
                if hasattr(ref_layer, 'is_tilemap') and ref_layer.is_tilemap():
                    from src.tilemap import TilemapLayer
                    tl = TilemapLayer(ref_layer.name, self.width, self.height,
                                      ref_layer.tileset)
                    tl.visible = ref_layer.visible
                    tl.locked = ref_layer.locked
                    tl.opacity = ref_layer.opacity
                    new_frame.layers[i] = tl
```

Apply same pattern to `insert_frame()`.

- [ ] **Step 3: Guard merge_down_in_all()**

In `src/animation.py:221-230`, before writing merged pixels, check if target is tilemap:

```python
                # If either layer is a tilemap, rasterize first
                if hasattr(above, 'is_tilemap') and above.is_tilemap():
                    above_layer = Layer(above.name, self.width, self.height)
                    above_layer.pixels._pixels = above.render_to_pixels()
                    above_layer.visible = above.visible
                    above_layer.opacity = above.opacity
                    above_layer.blend_mode = above.blend_mode
                else:
                    above_layer = above
                merged = flatten_layers([below, above_layer], self.width, self.height)
                # Result replaces below as a plain Layer
                if hasattr(below, 'is_tilemap') and below.is_tilemap():
                    new_below = Layer(below.name, self.width, self.height)
                    new_below.pixels._pixels = merged._pixels.copy()
                    new_below.visible = below.visible
                    new_below.opacity = below.opacity
                    frame.layers[index - 1] = new_below
                else:
                    below.pixels._pixels = merged._pixels.copy()
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/animation.py
git commit -m "feat: guard sync_layers, add_frame, merge_down for TilemapLayer"
```

---

### Task 11: Tilemap Serialization (Project v3)

**Files:**
- Modify: `src/project.py` — save/load tilemap layers and tilesets
- Modify: `src/animation.py` — add tilesets dict to AnimationTimeline

- [ ] **Step 1: Add tilesets dict to AnimationTimeline**

In `src/animation.py:71-77`, add to `__init__`:

```python
        self.tilesets: dict[str, object] = {}  # name -> Tileset (project-scoped)
```

- [ ] **Step 2: Update save_project() for tilemap support**

In `src/project.py`, add tileset serialization:

```python
    # Serialize tilesets
    import base64, io
    tilesets_data = {}
    for name, ts in getattr(timeline, 'tilesets', {}).items():
        tiles_encoded = []
        for tile in ts.tiles:
            img = Image.fromarray(tile, "RGBA")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            tiles_encoded.append(base64.b64encode(buf.getvalue()).decode("ascii"))
        tilesets_data[name] = {
            "tile_width": ts.tile_width,
            "tile_height": ts.tile_height,
            "tiles": tiles_encoded,
        }
```

For tilemap layers, serialize the grid instead of pixels:

```python
            # Check if layer is a tilemap
            if hasattr(layer, 'is_tilemap') and layer.is_tilemap():
                grid_data = [[ref.pack() for ref in row] for row in layer.grid]
                layers_data.append({
                    "name": layer.name,
                    "type": "tilemap",
                    "tileset_name": layer.tileset.name,
                    "grid": grid_data,
                    "visible": layer.visible,
                    "opacity": layer.opacity,
                    "blend_mode": layer.blend_mode,
                    "locked": layer.locked,
                    "depth": layer.depth,
                    "is_group": False,
                    "effects": [fx.to_dict() for fx in getattr(layer, 'effects', [])],
                    "edit_mode": layer.edit_mode,
                    "pixel_sub_mode": layer.pixel_sub_mode,
                })
                continue
```

- [ ] **Step 3: Update load_project() for tilemap support**

Deserialize tilesets first, then create TilemapLayer when `type == "tilemap"`:

```python
                if layer_data.get("type") == "tilemap":
                    from src.tilemap import TilemapLayer, TileRef
                    ts_name = layer_data["tileset_name"]
                    ts = timeline.tilesets.get(ts_name)
                    if ts:
                        layer = TilemapLayer(layer_data["name"], w, h, ts)
                        layer.grid = [
                            [TileRef.unpack(v) for v in row]
                            for row in layer_data["grid"]
                        ]
                        layer.edit_mode = layer_data.get("edit_mode", "pixels")
                        layer.pixel_sub_mode = layer_data.get("pixel_sub_mode", "auto")
                    else:
                        layer = Layer(layer_data["name"], w, h)  # fallback
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/project.py src/animation.py
git commit -m "feat: serialize tilemap layers and tilesets in project v3"
```

---

### Task 12: Tiles Panel UI + New Tilemap Layer Dialog

**Files:**
- Create: `src/ui/tiles_panel.py`
- Modify: `src/ui/right_panel.py` — mount tiles panel
- Modify: `src/app.py` — add tilemap layer creation, mode toggle

- [ ] **Step 1: Create tiles_panel.py**

A Tkinter Frame containing:
- Grid of tile thumbnail buttons (Canvas items showing each tile's pixels)
- Selected tile highlighted with green border
- Flip X / Flip Y toggle buttons
- Import button (opens file dialog → `Tileset.import_from_image()`)
- Visible only when active layer is a TilemapLayer

- [ ] **Step 2: Create New Tilemap Layer dialog**

In app.py or a separate dialog, a Toplevel with:
- Radio buttons: Create New / Use Existing tileset
- Tile size: width/height Spinboxes + presets dropdown (8x8, 16x16, 24x24, 32x32)
- Tileset name Entry
- Create/Cancel buttons
- On create: instantiate Tileset, register in `timeline.tilesets`, create TilemapLayer, add to all frames

- [ ] **Step 3: Wire mode toggle**

In app.py:
- Register keybinding for tilemap mode toggle (default: Tab when tilemap layer active)
- Cycle through: "pixels" (Auto) → "pixels" (Manual) → "tiles" → back to Auto
- Show current mode in status bar

- [ ] **Step 4: Mount tiles panel in right sidebar**

In `src/ui/right_panel.py`, conditionally show TilesPanel when active layer is tilemap.

- [ ] **Step 5: Test interactively**

Launch app, create tilemap layer via menu, verify tiles panel appears, switch modes, place tiles.

- [ ] **Step 6: Commit**

```bash
git add src/ui/tiles_panel.py src/ui/right_panel.py src/app.py
git commit -m "feat: add tiles panel, tilemap layer dialog, and mode toggle"
```

---

### Task 13: Tile Drawing Tools + Canvas Grid Overlay

**Files:**
- Modify: `src/tools.py` — add tile-mode behavior for Pen, Eraser, Fill
- Modify: `src/canvas.py` — add tile grid overlay rendering
- Modify: `src/app.py` — route mouse events to tile/pixel mode handlers

- [ ] **Step 1: Add tile grid overlay to canvas.py**

Add a method `draw_tile_grid()` to `PixelCanvas` that draws dashed lines at tile boundaries:
- Color: semi-transparent cyan (#00d4ff at 40% opacity)
- Only drawn when zoom makes each tile ≥ 8px on screen
- Cached — only redrawn on zoom/scroll change

- [ ] **Step 2: Add tile-mode tool behavior**

In app.py mouse event handlers, when active layer is tilemap and `edit_mode == "tiles"`:
- Convert mouse position to tile grid coordinates: `col = x // tile_width`, `row = y // tile_height`
- Pen tool: set `grid[row][col] = TileRef(selected_tile_index, flip_x, flip_y)`
- Eraser tool: set `grid[row][col] = TileRef(0)`
- Fill tool: flood-fill matching tile indices in grid
- Pick tool: read tile index from grid cell, set as selected tile

- [ ] **Step 3: Add pixel-mode tile awareness**

When active layer is tilemap and `edit_mode == "pixels"`:
- In Auto mode: after each stroke, extract modified tile cells, check if matching tile exists in tileset (or create new)
- In Manual mode: drawing modifies the tile definition directly in the tileset (all instances update)

- [ ] **Step 4: Add tile cursor preview**

In Tiles mode, when hovering over the canvas, draw a ghost preview of the selected tile at the hovered grid cell position.

- [ ] **Step 5: Test interactively**

Launch app, create tilemap layer, switch to Tiles mode, place tiles, verify grid overlay, test Pen/Eraser/Fill, switch to Pixels mode, draw, verify tile updates.

- [ ] **Step 6: Commit**

```bash
git add src/tools.py src/canvas.py src/app.py
git commit -m "feat: add tile drawing tools, grid overlay, and tile cursor preview"
```

---

### Task 14: Final Integration Test

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS (250+ existing + all new tests)

- [ ] **Step 2: Interactive smoke test**

1. Launch app, create 32x32 canvas
2. Draw a sprite on Layer 1
3. Add Outline + Drop Shadow effects via FX button, verify preview
4. Create Tilemap Layer, import a tileset image, switch to Tiles mode, place tiles
5. Select sprite, Ctrl+T, rotate 45° with RotSprite, Enter to apply
6. Save project, close, reopen — verify all data preserved
7. Export GIF — verify effects applied in export

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: integration fixes for Batch 4"
```
