# Selection Transform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Photoshop-style selection transform (rotate, scale, skew) with handle zones, live preview, and RotSprite-quality commit.

**Architecture:** New `src/selection_transform.py` module owns all transform state and math. Input handler routes mouse events to transform mode when active. Canvas draws transform handles as an overlay. Ctrl+T either enters transform on a floating paste or floats the current selection first.

**Tech Stack:** Python, NumPy, Pillow (`Image.transform(AFFINE)`), existing `src/rotsprite.py`

**Spec:** `docs/superpowers/specs/2026-04-07-selection-transform-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/selection_transform.py` | **Create** | `SelectionTransform` dataclass, affine matrix math, preview/final render, hit testing, bounding box |
| `src/canvas.py` | **Modify** | `draw_transform_handles()`, `clear_transform_handles()`, `hit_test_transform_handle()` |
| `src/input_handler.py` | **Modify** | Transform mode mouse routing (click/drag/release), commit/cancel, Ctrl+T dispatch |
| `src/app.py` | **Modify** | `self._selection_transform` state, Ctrl+T binding update, context bar, escape/enter routing |
| `tests/test_selection_transform.py` | **Create** | Unit tests for all transform math, hit testing, render functions |

---

## Task 1: SelectionTransform Dataclass & Identity

**Files:**
- Create: `src/selection_transform.py`
- Create: `tests/test_selection_transform.py`

- [ ] **Step 1: Write the failing test for identity transform**

```python
# tests/test_selection_transform.py
"""Tests for selection transform math and hit testing."""
import pytest
import numpy as np
from PIL import Image

from src.selection_transform import SelectionTransform, compute_affine_preview


def _make_test_image(w: int, h: int, color=(255, 0, 0, 255)) -> Image.Image:
    """Create a solid RGBA test image."""
    img = Image.new("RGBA", (w, h), color)
    return img


class TestSelectionTransformDataclass:
    def test_identity_defaults(self):
        img = _make_test_image(4, 4)
        t = SelectionTransform(pixels=img, position=(0, 0))
        assert t.rotation == 0.0
        assert t.scale_x == 1.0
        assert t.scale_y == 1.0
        assert t.skew_x == 0.0
        assert t.skew_y == 0.0
        assert t.pivot == (2.0, 2.0)  # center of 4x4

    def test_identity_preview_returns_same_size(self):
        img = _make_test_image(8, 6)
        t = SelectionTransform(pixels=img, position=(0, 0))
        result = compute_affine_preview(t)
        assert result.size == (8, 6)

    def test_identity_preview_preserves_pixels(self):
        img = _make_test_image(4, 4, color=(255, 0, 0, 255))
        t = SelectionTransform(pixels=img, position=(0, 0))
        result = compute_affine_preview(t)
        arr = np.array(result)
        # All pixels should still be red
        assert arr[:, :, 0].min() == 255
        assert arr[:, :, 3].min() == 255
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_selection_transform.py::TestSelectionTransformDataclass -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.selection_transform'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/selection_transform.py
"""Selection transform: affine math, preview, hit testing."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from PIL import Image


@dataclass
class SelectionTransform:
    """Active transform state for a floating selection."""

    pixels: Image.Image                  # original RGBA pixels (untransformed)
    position: tuple[int, int]            # top-left (x, y) on canvas
    rotation: float = 0.0                # degrees
    scale_x: float = 1.0                # horizontal scale factor
    scale_y: float = 1.0                # vertical scale factor
    skew_x: float = 0.0                 # horizontal skew in degrees
    skew_y: float = 0.0                 # vertical skew in degrees
    pivot: tuple[float, float] = field(default=None)  # type: ignore[assignment]
    source: str = "paste"               # "paste" or "float" — how it was created

    def __post_init__(self):
        if self.pivot is None:
            w, h = self.pixels.size
            self.pivot = (w / 2.0, h / 2.0)

    @property
    def is_identity(self) -> bool:
        return (self.rotation == 0.0 and self.scale_x == 1.0 and
                self.scale_y == 1.0 and self.skew_x == 0.0 and
                self.skew_y == 0.0)


def compute_affine_preview(transform: SelectionTransform) -> Image.Image:
    """Fast preview using Pillow AFFINE with nearest-neighbor.

    Transform chain: skew -> scale -> rotate (around pivot).
    Returns a new RGBA Image.
    """
    src = transform.pixels
    if transform.is_identity:
        return src.copy()

    w, h = src.size
    px, py = transform.pivot

    # Build combined affine: output-to-input mapping
    # Pillow's AFFINE expects (a, b, c, d, e, f) where:
    #   x_in = a*x_out + b*y_out + c
    #   y_in = d*x_out + e*y_out + f

    # Forward chain: translate to pivot -> skew -> scale -> rotate -> translate back
    # We need the inverse for Pillow (output-to-input)

    rad = math.radians(-transform.rotation)
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)

    sx = transform.scale_x if transform.scale_x != 0 else 0.001
    sy = transform.scale_y if transform.scale_y != 0 else 0.001

    skx = math.tan(math.radians(transform.skew_x))
    sky = math.tan(math.radians(transform.skew_y))

    # New dimensions to fit the transformed content
    corners = [(0, 0), (w, 0), (w, h), (0, h)]
    transformed = []
    for cx, cy in corners:
        # Apply forward transform to find output bounds
        dx, dy = cx - px, cy - py
        # Skew
        dx, dy = dx + skx * dy, dy + sky * dx
        # Scale
        dx, dy = dx * sx, dy * sy
        # Rotate
        rx = dx * cos_r - dy * sin_r
        ry = dx * sin_r + dy * cos_r
        transformed.append((rx + px, ry + py))

    xs = [p[0] for p in transformed]
    ys = [p[1] for p in transformed]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    out_w = max(1, int(math.ceil(max_x - min_x)))
    out_h = max(1, int(math.ceil(max_y - min_y)))

    # Inverse transform: from output coords back to input coords
    # Output pixel at (ox, oy) maps to input after undoing:
    #   translate to output origin -> translate to pivot -> inv-rotate -> inv-scale -> inv-skew -> translate back

    # For the inverse we reverse the chain
    inv_cos = math.cos(-rad)
    inv_sin = math.sin(-rad)

    # Build the 3x3 inverse matrix step by step
    # Step 1: translate output pixel by min offset to get canvas-relative
    # Step 2: subtract pivot
    # Step 3: inverse rotate
    # Step 4: inverse scale
    # Step 5: inverse skew
    # Step 6: add pivot back

    # Combined as 2x3 affine coefficients for Pillow:
    # We compute this numerically for clarity
    def _inv_transform(ox, oy):
        """Map output coord to input coord."""
        # Offset from output image origin to canvas coords
        cx = ox + min_x
        cy = oy + min_y
        # Translate to pivot-relative
        dx = cx - px
        dy = cy - py
        # Inverse rotate
        rx = dx * inv_cos - dy * inv_sin
        ry = dx * inv_sin + dy * inv_cos
        # Inverse scale
        rx = rx / sx
        ry = ry / sy
        # Inverse skew
        # Forward skew: x' = x + skx*y, y' = y + sky*x
        # Inverse: x = (x' - skx*y') / (1 - skx*sky), same for y
        det = 1.0 - skx * sky
        if abs(det) < 1e-10:
            det = 1e-10
        ix = (rx - skx * ry) / det
        iy = (ry - sky * rx) / det
        # Translate back from pivot
        return ix + px, iy + py

    # Extract affine coefficients from two known point mappings
    # (0,0), (1,0), (0,1) in output -> input
    x00, y00 = _inv_transform(0, 0)
    x10, y10 = _inv_transform(1, 0)
    x01, y01 = _inv_transform(0, 1)

    a = x10 - x00  # dx_in / dx_out
    b = x01 - x00  # dx_in / dy_out
    c = x00         # offset x
    d = y10 - y00   # dy_in / dx_out
    e = y01 - y00   # dy_in / dy_out
    f = y00         # offset y

    result = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    result = src.transform(
        (out_w, out_h), Image.AFFINE,
        (a, b, c, d, e, f),
        resample=Image.NEAREST,
        fillcolor=(0, 0, 0, 0),
    )
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_selection_transform.py::TestSelectionTransformDataclass -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/selection_transform.py tests/test_selection_transform.py
git commit -m "feat: add SelectionTransform dataclass and identity preview"
```

---

## Task 2: Affine Preview — Rotation, Scale, Skew

**Files:**
- Modify: `tests/test_selection_transform.py`
- File already exists: `src/selection_transform.py`

- [ ] **Step 1: Write failing tests for rotation, scale, and skew**

```python
# Add to tests/test_selection_transform.py

class TestAffinePreview:
    def test_rotation_90_swaps_dimensions(self):
        img = _make_test_image(8, 4)
        t = SelectionTransform(pixels=img, position=(0, 0), rotation=90.0)
        result = compute_affine_preview(t)
        # 90° rotation of 8x4 should produce ~4x8
        assert abs(result.size[0] - 4) <= 1
        assert abs(result.size[1] - 8) <= 1

    def test_scale_2x_doubles_dimensions(self):
        img = _make_test_image(4, 4)
        t = SelectionTransform(pixels=img, position=(0, 0), scale_x=2.0, scale_y=2.0)
        result = compute_affine_preview(t)
        assert result.size == (8, 8)

    def test_scale_non_uniform(self):
        img = _make_test_image(4, 4)
        t = SelectionTransform(pixels=img, position=(0, 0), scale_x=2.0, scale_y=1.0)
        result = compute_affine_preview(t)
        assert result.size == (8, 4)

    def test_skew_horizontal_changes_width(self):
        img = _make_test_image(4, 4)
        t = SelectionTransform(pixels=img, position=(0, 0), skew_x=45.0)
        result = compute_affine_preview(t)
        # 45° skew adds up to h pixels of width
        assert result.size[0] > 4

    def test_scale_down_halves(self):
        img = _make_test_image(8, 8)
        t = SelectionTransform(pixels=img, position=(0, 0), scale_x=0.5, scale_y=0.5)
        result = compute_affine_preview(t)
        assert result.size == (4, 4)

    def test_rotation_preserves_alpha(self):
        """Rotated image should have transparent background."""
        img = _make_test_image(4, 4, color=(255, 0, 0, 255))
        t = SelectionTransform(pixels=img, position=(0, 0), rotation=45.0)
        result = compute_affine_preview(t)
        arr = np.array(result)
        # Corners of rotated square should be transparent
        assert arr[0, 0, 3] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_selection_transform.py::TestAffinePreview -v`
Expected: PASS — these should pass with the existing `compute_affine_preview` implementation from Task 1. If any fail, fix the affine math.

- [ ] **Step 3: Commit**

```bash
git add tests/test_selection_transform.py
git commit -m "test: add affine preview tests for rotation, scale, skew"
```

---

## Task 3: Final Quality Render (RotSprite)

**Files:**
- Modify: `src/selection_transform.py`
- Modify: `tests/test_selection_transform.py`

- [ ] **Step 1: Write failing test for final render**

```python
# Add to tests/test_selection_transform.py
from src.selection_transform import compute_affine_final


class TestAffineFinal:
    def test_final_identity_same_as_preview(self):
        img = _make_test_image(4, 4)
        t = SelectionTransform(pixels=img, position=(0, 0))
        preview = compute_affine_preview(t)
        final = compute_affine_final(t)
        assert final.size == preview.size

    def test_final_rotation_uses_rotsprite(self):
        """Final render with rotation should produce result (may differ from preview due to RotSprite)."""
        img = _make_test_image(8, 8, color=(255, 0, 0, 255))
        t = SelectionTransform(pixels=img, position=(0, 0), rotation=30.0)
        result = compute_affine_final(t)
        assert result.mode == "RGBA"
        assert result.size[0] > 0 and result.size[1] > 0

    def test_final_scale_only_no_rotsprite(self):
        """Scale-only transform should not invoke RotSprite (just affine)."""
        img = _make_test_image(4, 4)
        t = SelectionTransform(pixels=img, position=(0, 0), scale_x=2.0, scale_y=2.0)
        result = compute_affine_final(t)
        assert result.size == (8, 8)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_selection_transform.py::TestAffineFinal -v`
Expected: FAIL — `ImportError: cannot import name 'compute_affine_final'`

- [ ] **Step 3: Implement compute_affine_final**

Add to `src/selection_transform.py`:

```python
from src.rotsprite import rotsprite_rotate


def compute_affine_final(transform: SelectionTransform) -> Image.Image:
    """High-quality final render: RotSprite for rotation, AFFINE for scale/skew.

    Strategy: apply skew+scale via Pillow AFFINE first (on original pixels),
    then rotate the result with RotSprite. This matches the spec's transform
    chain (skew -> scale -> rotate) and ensures preview/final consistency.
    """
    if transform.is_identity:
        return transform.pixels.copy()

    has_rotation = transform.rotation % 360 != 0
    has_scale_skew = (transform.scale_x != 1.0 or transform.scale_y != 1.0 or
                      transform.skew_x != 0.0 or transform.skew_y != 0.0)

    if has_scale_skew:
        # Apply skew+scale first via Pillow AFFINE (no rotation)
        pre_rotate = SelectionTransform(
            pixels=transform.pixels,
            position=transform.position,
            rotation=0.0,
            scale_x=transform.scale_x,
            scale_y=transform.scale_y,
            skew_x=transform.skew_x,
            skew_y=transform.skew_y,
            pivot=transform.pivot,
        )
        scaled_img = compute_affine_preview(pre_rotate)
    else:
        scaled_img = transform.pixels

    if has_rotation:
        # Apply RotSprite rotation to the scaled/skewed result
        pixels_arr = np.array(scaled_img)
        w, h = scaled_img.size
        # Pivot must be re-centered for the new image dimensions
        px, py = w // 2, h // 2
        rotated_arr = rotsprite_rotate(pixels_arr, transform.rotation, pivot=(px, py))
        return Image.fromarray(rotated_arr, "RGBA")
    else:
        return scaled_img
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_selection_transform.py::TestAffineFinal -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/selection_transform.py tests/test_selection_transform.py
git commit -m "feat: add compute_affine_final with RotSprite for rotation quality"
```

---

## Task 4: Bounding Box & Hit Testing

**Files:**
- Modify: `src/selection_transform.py`
- Modify: `tests/test_selection_transform.py`

- [ ] **Step 1: Write failing tests for bounding box and hit testing**

```python
# Add to tests/test_selection_transform.py
from src.selection_transform import (
    get_transform_bounding_box, hit_test_transform_handle,
)


class TestBoundingBox:
    def test_identity_bounding_box(self):
        img = _make_test_image(10, 8)
        t = SelectionTransform(pixels=img, position=(5, 3))
        corners = get_transform_bounding_box(t)
        assert len(corners) == 4
        # Top-left, top-right, bottom-right, bottom-left in canvas coords
        assert corners[0] == pytest.approx((5, 3), abs=0.1)
        assert corners[1] == pytest.approx((15, 3), abs=0.1)
        assert corners[2] == pytest.approx((15, 11), abs=0.1)
        assert corners[3] == pytest.approx((5, 11), abs=0.1)

    def test_scaled_bounding_box(self):
        img = _make_test_image(4, 4)
        t = SelectionTransform(pixels=img, position=(0, 0), scale_x=2.0, scale_y=2.0)
        corners = get_transform_bounding_box(t)
        # Scaled 2x from center pivot (2,2): corners go from -2,-2 to 6,6
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        assert max(xs) - min(xs) == pytest.approx(8.0, abs=0.5)
        assert max(ys) - min(ys) == pytest.approx(8.0, abs=0.5)


class TestHitTest:
    def _make_transform(self):
        """10x10 image at position (10, 10) => corners at (10,10), (20,10), (20,20), (10,20)."""
        img = _make_test_image(10, 10)
        return SelectionTransform(pixels=img, position=(10, 10))

    def test_hit_corner_0(self):
        t = self._make_transform()
        # pixel_size=1, corner 0 is at canvas (10, 10) => screen (10, 10)
        result = hit_test_transform_handle(t, 10, 10, pixel_size=1)
        assert result == "corner:0"

    def test_hit_corner_2(self):
        t = self._make_transform()
        result = hit_test_transform_handle(t, 20, 20, pixel_size=1)
        assert result == "corner:2"

    def test_hit_midpoint_top(self):
        t = self._make_transform()
        # Midpoint top is at (15, 10)
        result = hit_test_transform_handle(t, 15, 10, pixel_size=1)
        assert result == "midpoint:top"

    def test_hit_midpoint_right(self):
        t = self._make_transform()
        result = hit_test_transform_handle(t, 20, 15, pixel_size=1)
        assert result == "midpoint:right"

    def test_hit_inside(self):
        t = self._make_transform()
        # Use (13, 13) to avoid hitting the pivot at (15, 15)
        result = hit_test_transform_handle(t, 13, 13, pixel_size=1)
        assert result == "inside"

    def test_hit_outside(self):
        t = self._make_transform()
        result = hit_test_transform_handle(t, 2, 2, pixel_size=1)
        assert result == "outside"

    def test_hit_pivot(self):
        t = self._make_transform()
        # Pivot is at center of image: position + pivot = (10+5, 10+5) = (15, 15)
        # But "inside" might take priority — pivot has highest priority in the function
        result = hit_test_transform_handle(t, 15, 15, pixel_size=1, threshold=2.0)
        assert result == "pivot"

    def test_hit_none_far_away(self):
        t = self._make_transform()
        # Very far away, outside the expanded hit region
        result = hit_test_transform_handle(t, 500, 500, pixel_size=1)
        assert result == "outside"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_selection_transform.py::TestBoundingBox tests/test_selection_transform.py::TestHitTest -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement bounding box and hit testing**

Add to `src/selection_transform.py`:

```python
def get_transform_bounding_box(transform: SelectionTransform) -> list[tuple[float, float]]:
    """Return 4 corners of the transformed bounding box in canvas coordinates.

    Returns: [(x,y), (x,y), (x,y), (x,y)] — TL, TR, BR, BL order.
    """
    w, h = transform.pixels.size
    ox, oy = transform.position
    px, py = transform.pivot

    # Local corners (relative to image origin)
    local_corners = [(0, 0), (w, 0), (w, h), (0, h)]

    rad = math.radians(transform.rotation)
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)
    skx = math.tan(math.radians(transform.skew_x))
    sky = math.tan(math.radians(transform.skew_y))

    result = []
    for lx, ly in local_corners:
        # Relative to pivot
        dx, dy = lx - px, ly - py
        # Skew
        dx, dy = dx + skx * dy, dy + sky * dx
        # Scale
        dx, dy = dx * transform.scale_x, dy * transform.scale_y
        # Rotate
        rx = dx * cos_r - dy * sin_r
        ry = dx * sin_r + dy * cos_r
        # Translate to canvas coords
        result.append((rx + px + ox, ry + py + oy))

    return result


def hit_test_transform_handle(transform: SelectionTransform,
                               canvas_x: float, canvas_y: float,
                               pixel_size: int,
                               threshold: float = 8.0) -> str | None:
    """Test what zone a canvas coordinate hits.

    Args:
        transform: Active SelectionTransform
        canvas_x, canvas_y: Position in canvas coordinates (grid pixels)
        pixel_size: Zoom level (screen pixels per grid pixel)
        threshold: Hit distance in canvas pixels

    Returns: "corner:0"-"corner:3", "midpoint:top/right/bottom/left",
             "pivot", "inside", "outside", or None
    """
    corners = get_transform_bounding_box(transform)
    ox, oy = transform.position
    px, py = transform.pivot

    # Canvas-space pivot
    pivot_cx = px + ox
    pivot_cy = py + oy

    # 1. Check pivot (highest priority, smallest target)
    if math.hypot(canvas_x - pivot_cx, canvas_y - pivot_cy) <= threshold:
        return "pivot"

    # 2. Check corners
    for i, (cx, cy) in enumerate(corners):
        if math.hypot(canvas_x - cx, canvas_y - cy) <= threshold:
            return f"corner:{i}"

    # 3. Check midpoints
    midpoints = {
        "top": ((corners[0][0] + corners[1][0]) / 2, (corners[0][1] + corners[1][1]) / 2),
        "right": ((corners[1][0] + corners[2][0]) / 2, (corners[1][1] + corners[2][1]) / 2),
        "bottom": ((corners[2][0] + corners[3][0]) / 2, (corners[2][1] + corners[3][1]) / 2),
        "left": ((corners[3][0] + corners[0][0]) / 2, (corners[3][1] + corners[0][1]) / 2),
    }
    for name, (mx, my) in midpoints.items():
        if math.hypot(canvas_x - mx, canvas_y - my) <= threshold:
            return f"midpoint:{name}"

    # 4. Check inside bounding box using cross-product point-in-polygon
    def _cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    point = (canvas_x, canvas_y)
    # Check if point is inside the quadrilateral (all cross products same sign)
    signs = []
    for i in range(4):
        cp = _cross(corners[i], corners[(i + 1) % 4], point)
        signs.append(cp >= 0)
    if all(signs) or not any(signs):
        return "inside"

    # 5. Everything else is "outside"
    return "outside"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_selection_transform.py::TestBoundingBox tests/test_selection_transform.py::TestHitTest -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/selection_transform.py tests/test_selection_transform.py
git commit -m "feat: add transform bounding box and hit testing with zone detection"
```

---

## Task 5: Canvas Transform Handle Drawing

**Files:**
- Modify: `src/canvas.py` (add `draw_transform_handles`, `clear_transform_handles`)

- [ ] **Step 1: Write a smoke test for handle drawing**

```python
# Add to tests/test_selection_transform.py
import tkinter as tk

class TestCanvasHandles:
    def test_draw_transform_handles_no_error(self):
        """Smoke test: drawing handles should not raise."""
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            pytest.skip("No display available")

        from src.canvas import PixelCanvas
        from src.pixel_data import PixelGrid
        grid = PixelGrid(25, 25)
        canvas = PixelCanvas(root, grid=grid, pixel_size=4)

        img = _make_test_image(10, 10)
        t = SelectionTransform(pixels=img, position=(5, 5))
        corners = get_transform_bounding_box(t)

        canvas.draw_transform_handles(corners, t.pivot, t.position, canvas.pixel_size)
        # Should have created canvas items
        items = canvas.find_withtag("transform_handle")
        assert len(items) > 0

        canvas.clear_transform_handles()
        items = canvas.find_withtag("transform_handle")
        assert len(items) == 0

        root.destroy()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_selection_transform.py::TestCanvasHandles -v`
Expected: FAIL — `AttributeError: 'PixelCanvas' object has no attribute 'draw_transform_handles'`

- [ ] **Step 3: Implement draw_transform_handles in canvas.py**

Add after `clear_rotation_handles` (around line 534) in `src/canvas.py`:

```python
    # --- Selection Transform Handle Overlay ---

    def draw_transform_handles(self, corners: list[tuple[float, float]],
                                pivot: tuple[float, float],
                                position: tuple[int, int],
                                zoom: int) -> None:
        """Draw transform bounding box with corner circles, midpoint squares, and pivot.

        Args:
            corners: 4 canvas-coordinate corners from get_transform_bounding_box
            pivot: (px, py) pivot relative to image origin
            position: (x, y) canvas position of the transform
            zoom: pixel_size (screen pixels per grid pixel)
        """
        self.delete("transform_handle")
        ps = zoom

        # Convert canvas coords to screen coords
        sc = [(cx * ps, cy * ps) for cx, cy in corners]

        # Draw dashed bounding box lines
        for i in range(4):
            x0, y0 = sc[i]
            x1, y1 = sc[(i + 1) % 4]
            self.create_line(x0, y0, x1, y1,
                             fill="#00f0ff", dash=(6, 3), width=2,
                             tags="transform_handle")

        # Corner circles (filled, for scale)
        handle_r = 4
        for sx, sy in sc:
            self.create_oval(sx - handle_r, sy - handle_r,
                             sx + handle_r, sy + handle_r,
                             fill="#00f0ff", outline="#ffffff", width=1,
                             tags="transform_handle")

        # Midpoint squares (for axis scale)
        sq_r = 3
        for i in range(4):
            mx = (sc[i][0] + sc[(i + 1) % 4][0]) / 2
            my = (sc[i][1] + sc[(i + 1) % 4][1]) / 2
            self.create_rectangle(mx - sq_r, my - sq_r,
                                  mx + sq_r, my + sq_r,
                                  fill="#00f0ff", outline="#ffffff", width=1,
                                  tags="transform_handle")

        # Pivot dot (magenta circle)
        pvx = (position[0] + pivot[0]) * ps
        pvy = (position[1] + pivot[1]) * ps
        pivot_r = 3
        self.create_oval(pvx - pivot_r, pvy - pivot_r,
                         pvx + pivot_r, pvy + pivot_r,
                         fill="#ff00ff", outline="#ffffff", width=1,
                         tags="transform_handle")

        self.tag_raise("transform_handle")

    def clear_transform_handles(self) -> None:
        """Remove selection transform overlay handles."""
        self.delete("transform_handle")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_selection_transform.py::TestCanvasHandles -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/canvas.py tests/test_selection_transform.py
git commit -m "feat: add transform handle drawing to canvas (corners, midpoints, pivot)"
```

---

## Task 6: App State & Ctrl+T Binding

**Files:**
- Modify: `src/app.py` (lines 194-204 for state, line 633-634 for binding)

This task adds the `_selection_transform` state variable and rewires Ctrl+T to dispatch to either selection transform or layer rotation.

- [ ] **Step 1: Add selection transform state to app.py**

In `src/app.py`, after the rotation state block (line 204), add:

```python
        # Selection transform state
        self._selection_transform = None   # SelectionTransform or None
```

- [ ] **Step 2: Update Ctrl+T binding to dispatch**

Replace the Ctrl+T binding (lines 633-634) with:

```python
        for key in ("<Control-t>", "<Control-T>"):
            self.root.bind(key, lambda e: self._enter_selection_transform())
```

- [ ] **Step 3: Initialize all transform state variables**

Also in `src/app.py`, after `self._selection_transform`, add:

```python
        self._transform_context_frame = None
        self._transform_drag_zone = None
        self._transform_drag_start = None
        self._transform_start_state = None
        self._transform_mouse_start_angle = 0.0
        self._transform_ctrl_held = False
        self._transform_shift_held = False
```

Note: Do NOT add `from src.selection_transform import SelectionTransform` to `app.py` — it is only needed inside `input_handler.py` via local imports.

- [ ] **Step 4: Run existing tests to verify no regressions**

Run: `python -m pytest tests/ -x -q`
Expected: All existing tests pass

- [ ] **Step 5: Commit**

```bash
git add src/app.py
git commit -m "feat: add selection transform state and rewire Ctrl+T binding"
```

---

## Task 7: Transform Mode Entry, Commit, and Cancel (InputHandler)

**Files:**
- Modify: `src/input_handler.py`

This is the core integration task. It adds `_enter_selection_transform`, `_commit_selection_transform`, `_cancel_selection_transform`, and wires up mouse event routing.

- [ ] **Step 1: Write tests for enter/commit/cancel flow**

```python
# Add to tests/test_selection_transform.py

class TestTransformFlow:
    """Test the high-level enter/commit/cancel logic."""

    def test_commit_clips_to_canvas(self):
        """Transformed pixels outside canvas bounds are discarded on commit."""
        from src.selection_transform import clip_to_canvas
        from src.pixel_data import PixelGrid

        img = _make_test_image(4, 4, color=(255, 0, 0, 255))
        # Place at position (-2, -2) — half the image is outside
        grid = PixelGrid(4, 4)
        clip_to_canvas(img, (-2, -2), grid)

        # Only the 2x2 visible portion should be pasted
        assert tuple(grid.get_pixel(0, 0)) == (255, 0, 0, 255)
        assert tuple(grid.get_pixel(1, 1)) == (255, 0, 0, 255)

    def test_commit_identity_pastes_original(self):
        """Identity transform commit pastes original pixels unchanged."""
        from src.selection_transform import clip_to_canvas
        from src.pixel_data import PixelGrid

        img = _make_test_image(3, 3, color=(0, 255, 0, 255))
        grid = PixelGrid(10, 10)
        clip_to_canvas(img, (2, 2), grid)

        assert tuple(grid.get_pixel(2, 2)) == (0, 255, 0, 255)
        assert tuple(grid.get_pixel(4, 4)) == (0, 255, 0, 255)
        # Outside the pasted region should be transparent
        assert grid.get_pixel(0, 0)[3] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_selection_transform.py::TestTransformFlow -v`
Expected: FAIL — `ImportError: cannot import name 'clip_to_canvas'`

- [ ] **Step 3: Implement clip_to_canvas in selection_transform.py**

Add to `src/selection_transform.py`:

```python
from src.pixel_data import PixelGrid


def clip_to_canvas(image: Image.Image, position: tuple[int, int],
                   target: PixelGrid) -> None:
    """Paste an RGBA image onto a PixelGrid, clipping to canvas bounds.

    Only non-transparent pixels are pasted. Pixels outside canvas bounds
    are silently discarded.

    Args:
        image: RGBA PIL Image to paste
        position: (x, y) top-left canvas coordinate
        target: Destination PixelGrid
    """
    arr = np.array(image)
    ih, iw = arr.shape[:2]
    ox, oy = position

    # Compute visible region
    src_x0 = max(0, -ox)
    src_y0 = max(0, -oy)
    src_x1 = min(iw, target.width - ox)
    src_y1 = min(ih, target.height - oy)

    if src_x0 >= src_x1 or src_y0 >= src_y1:
        return  # Entirely outside canvas

    dst_x0 = ox + src_x0
    dst_y0 = oy + src_y0

    region = arr[src_y0:src_y1, src_x0:src_x1]
    # Paste non-transparent pixels using NumPy ops (no Python loops)
    dst_slice = target._pixels[dst_y0:dst_y0 + region.shape[0],
                               dst_x0:dst_x0 + region.shape[1]]
    mask = region[:, :, 3] > 0
    dst_slice[mask] = region[mask]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_selection_transform.py::TestTransformFlow -v`
Expected: PASS

- [ ] **Step 5: Add transform mode methods to input_handler.py**

Add the following methods to `InputHandlerMixin` in `src/input_handler.py`.

**Important:** These are added as new methods. They do NOT conflict with any existing mixin method names.

```python
    def _enter_selection_transform(self):
        """Enter selection transform mode via Ctrl+T.

        - If already in transform mode: no-op
        - If floating paste exists: create transform from paste
        - If selection exists: float it (cut from layer), then create transform
        - Otherwise: fall back to layer rotation mode
        """
        from src.selection_transform import SelectionTransform

        if self._selection_transform is not None:
            return  # Already in transform mode

        if self._pasting and self._clipboard:
            # Convert floating paste into a transform
            img = self._clipboard.to_pil_image()
            self._selection_transform = SelectionTransform(
                pixels=img,
                position=self._paste_pos,
                source="paste",
            )
            self._pasting = False
            self.pixel_canvas.clear_floating()
            self._draw_transform_overlay()
            self._show_transform_context_bar()
            self._update_status("Transform: drag handles, Enter=apply, Esc=cancel")
            return

        if self._selection_pixels and len(self._selection_pixels) > 0:
            # Float the selection: cut pixels from layer into transform
            self._push_undo()
            xs = [p[0] for p in self._selection_pixels]
            ys = [p[1] for p in self._selection_pixels]
            x0, y0 = min(xs), min(ys)
            x1, y1 = max(xs), max(ys)
            w, h = x1 - x0 + 1, y1 - y0 + 1

            grid = self.timeline.current_layer()
            clip = PixelGrid(w, h)
            for (px, py) in self._selection_pixels:
                color = grid.get_pixel(px, py)
                clip.set_pixel(px - x0, py - y0, color)
                grid.set_pixel(px, py, (0, 0, 0, 0))  # Cut

            img = clip.to_pil_image()
            self._selection_transform = SelectionTransform(
                pixels=img,
                position=(x0, y0),
                source="float",
            )
            self._clear_selection()
            self._render_canvas()
            self._draw_transform_overlay()
            self._show_transform_context_bar()
            self._update_status("Transform: drag handles, Enter=apply, Esc=cancel")
            return

        # No selection or paste — fall back to layer rotation
        self._enter_rotation_mode()

    def _draw_transform_overlay(self):
        """Render the transform preview and handles on the canvas."""
        from src.selection_transform import (
            compute_affine_preview, get_transform_bounding_box,
        )
        t = self._selection_transform
        if t is None:
            return

        # Draw preview image
        preview = compute_affine_preview(t)
        preview_grid = PixelGrid.from_pil_image(preview)

        # Compute where the preview should be placed
        # The preview may be larger/offset from the original due to transforms
        corners = get_transform_bounding_box(t)
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        draw_x = int(min(xs))
        draw_y = int(min(ys))

        self.pixel_canvas.draw_floating_pixels(preview_grid, draw_x, draw_y)

        # Draw handles
        self.pixel_canvas.draw_transform_handles(
            corners, t.pivot, t.position, self.pixel_canvas.pixel_size)

    def _commit_selection_transform(self):
        """Apply the transform and paste onto the active layer."""
        from src.selection_transform import (
            compute_affine_final, get_transform_bounding_box, clip_to_canvas,
        )
        t = self._selection_transform
        if t is None:
            return

        self._push_undo()
        final_img = compute_affine_final(t)

        # Compute placement position from bounding box
        corners = get_transform_bounding_box(t)
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        place_x = int(min(xs))
        place_y = int(min(ys))

        grid = self.timeline.current_layer()
        clip_to_canvas(final_img, (place_x, place_y), grid)

        self._selection_transform = None
        self.pixel_canvas.clear_floating()
        self.pixel_canvas.clear_transform_handles()
        self._hide_transform_context_bar()
        self._render_canvas()
        self._update_status("Transform applied")

    def _cancel_selection_transform(self):
        """Cancel the transform, restoring original pixels if floated."""
        t = self._selection_transform
        if t is None:
            return

        if t.source == "float":
            # Paste original pixels back untransformed
            from src.selection_transform import clip_to_canvas
            grid = self.timeline.current_layer()
            clip_to_canvas(t.pixels, t.position, grid)

        self._selection_transform = None
        self.pixel_canvas.clear_floating()
        self.pixel_canvas.clear_transform_handles()
        self._hide_transform_context_bar()
        self._render_canvas()
        self._update_status("Transform cancelled")
```

- [ ] **Step 6: Wire transform mode into mouse event routing**

In `_on_canvas_click` (around line 49, after the rotation mode check), add:

```python
        # If in selection transform mode, handle transform interactions
        if self._selection_transform is not None:
            self._transform_handle_click(x, y, event_state)
            return
```

In `_on_canvas_drag` (around line 184, after the rotation drag check), add:

```python
        if self._selection_transform is not None:
            self._transform_handle_drag(x, y)
            return
```

In `_on_canvas_release` (around line 307, after the rotation release check), add:

```python
        if self._selection_transform is not None:
            self._transform_handle_release(x, y, event_state)
            return
```

- [ ] **Step 7: Wire transform into Escape and Enter handlers**

Update `_on_escape` (line 451) — add transform check before rotation:

```python
    def _on_escape(self):
        """Escape cancels transform/rotation/paste mode first, then clears selection."""
        if self._selection_transform is not None:
            self._cancel_selection_transform()
        elif self._rotation_mode:
            self._exit_rotation_mode(apply=False)
        elif self._pasting:
            self._cancel_paste()
        elif self._polygon_points:
            self._cancel_polygon()
        else:
            self._clear_selection()
```

Update `_on_enter_key` (line 462):

```python
    def _on_enter_key(self):
        """Enter applies transform/rotation if in mode."""
        if self._selection_transform is not None:
            self._commit_selection_transform()
        elif self._rotation_mode:
            self._exit_rotation_mode(apply=True)
        elif self._polygon_points:
            self._commit_polygon()
```

- [ ] **Step 8: Auto-show handles on paste**

Modify `_paste_clipboard` (line 589) to auto-enter transform mode:

```python
    def _paste_clipboard(self):
        """Enter floating paste mode with transform handles."""
        if self._clipboard is None:
            return
        from src.selection_transform import SelectionTransform

        self._pasting = False
        self._clear_selection()
        img = self._clipboard.to_pil_image()
        origin = self._paste_origin
        self._selection_transform = SelectionTransform(
            pixels=img,
            position=origin,
            source="paste",
        )
        self._draw_transform_overlay()
        self._show_transform_context_bar()
        self._update_status("Transform: drag handles, Enter=apply, Esc=cancel")
```

- [ ] **Step 9: Run all tests**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 10: Commit**

```bash
git add src/input_handler.py src/selection_transform.py
git commit -m "feat: add selection transform entry, commit, cancel, and event routing"
```

---

## Task 8: Mouse Interaction — Drag Handlers for All Zones

**Files:**
- Modify: `src/input_handler.py`

This adds the actual drag logic for each handle zone: corners for scale, midpoints for axis scale, outside for rotation, inside for move, pivot for reposition, Ctrl+corner for skew.

- [ ] **Step 1: Implement transform click/drag/release handlers**

Add to `InputHandlerMixin` in `src/input_handler.py`:

```python
    def _transform_handle_click(self, x, y, event_state=0):
        """Handle mouse click during selection transform mode."""
        from src.selection_transform import hit_test_transform_handle

        t = self._selection_transform
        hit = hit_test_transform_handle(t, x, y, self.pixel_canvas.pixel_size)

        self._transform_drag_zone = hit
        self._transform_drag_start = (x, y)
        self._transform_start_state = {
            "position": t.position,
            "rotation": t.rotation,
            "scale_x": t.scale_x,
            "scale_y": t.scale_y,
            "skew_x": t.skew_x,
            "skew_y": t.skew_y,
            "pivot": t.pivot,
        }

        if hit == "outside":
            # Record starting angle from mouse to pivot for rotation
            pvx = t.position[0] + t.pivot[0]
            pvy = t.position[1] + t.pivot[1]
            self._transform_mouse_start_angle = math.degrees(
                math.atan2(y - pvy, x - pvx))

        # Set cursor
        cursors = {
            "inside": "fleur",
            "outside": "exchange",
            "pivot": "crosshair",
        }
        if hit.startswith("corner:"):
            cursor = "sizing" if not (event_state & 0x0004) else "crosshair"  # Ctrl for skew
        elif hit.startswith("midpoint:"):
            if "top" in hit or "bottom" in hit:
                cursor = "sb_v_double_arrow"
            else:
                cursor = "sb_h_double_arrow"
        else:
            cursor = cursors.get(hit, "arrow")
        self.pixel_canvas.config(cursor=cursor)

    def _transform_handle_drag(self, x, y):
        """Handle mouse drag during selection transform mode."""
        t = self._selection_transform
        if t is None:
            return
        zone = getattr(self, '_transform_drag_zone', None)
        if zone is None:
            return

        start = self._transform_start_state
        sx, sy = self._transform_drag_start
        dx, dy = x - sx, y - sy

        if zone == "inside":
            # Move
            t.position = (start["position"][0] + dx,
                          start["position"][1] + dy)

        elif zone == "outside":
            # Rotate around pivot
            pvx = t.position[0] + t.pivot[0]
            pvy = t.position[1] + t.pivot[1]
            current_angle = math.degrees(math.atan2(y - pvy, x - pvx))
            delta = current_angle - self._transform_mouse_start_angle
            t.rotation = start["rotation"] + delta

        elif zone == "pivot":
            # Reposition pivot
            t.pivot = (start["pivot"][0] + dx, start["pivot"][1] + dy)

        elif zone.startswith("corner:"):
            ctrl_held = bool(self._transform_ctrl_held)
            shift_held = bool(getattr(self, '_transform_shift_held', False))
            if ctrl_held:
                # Skew — horizontal corners adjust skew_x, vertical adjust skew_y
                idx = int(zone.split(":")[1])
                if idx in (0, 1):  # Top corners → skew X
                    t.skew_x = start["skew_x"] + dx * 0.5
                else:  # Bottom corners → skew X (opposite direction)
                    t.skew_x = start["skew_x"] - dx * 0.5
            else:
                # Scale from center
                pvx = t.position[0] + t.pivot[0]
                pvy = t.position[1] + t.pivot[1]
                corner_idx = int(zone.split(":")[1])
                from src.selection_transform import get_transform_bounding_box
                orig_corners = get_transform_bounding_box(SelectionTransform(
                    pixels=t.pixels, position=start["position"],
                    rotation=start["rotation"],
                    scale_x=start["scale_x"], scale_y=start["scale_y"],
                    skew_x=start["skew_x"], skew_y=start["skew_y"],
                    pivot=start["pivot"],
                ))
                orig_corner = orig_corners[corner_idx]
                orig_dist = math.hypot(orig_corner[0] - pvx, orig_corner[1] - pvy)
                new_dist = math.hypot(x - pvx, y - pvy)
                if orig_dist > 0.1:
                    factor = new_dist / orig_dist
                    if shift_held:
                        # Shift = non-uniform: scale X and Y independently
                        x_dist = abs(x - pvx)
                        y_dist = abs(y - pvy)
                        orig_x_dist = abs(orig_corner[0] - pvx)
                        orig_y_dist = abs(orig_corner[1] - pvy)
                        if orig_x_dist > 0.1:
                            t.scale_x = start["scale_x"] * (x_dist / orig_x_dist)
                        if orig_y_dist > 0.1:
                            t.scale_y = start["scale_y"] * (y_dist / orig_y_dist)
                    else:
                        # Default = uniform scale
                        t.scale_x = start["scale_x"] * factor
                        t.scale_y = start["scale_y"] * factor

        elif zone.startswith("midpoint:"):
            # Non-uniform scale along one axis
            side = zone.split(":")[1]
            pvx = t.position[0] + t.pivot[0]
            pvy = t.position[1] + t.pivot[1]
            w, h = t.pixels.size
            if side in ("left", "right"):
                orig_half = (w / 2.0) * start["scale_x"]
                if orig_half > 0.1:
                    new_half = abs(x - pvx)
                    t.scale_x = start["scale_x"] * (new_half / orig_half)
            else:  # top, bottom
                orig_half = (h / 2.0) * start["scale_y"]
                if orig_half > 0.1:
                    new_half = abs(y - pvy)
                    t.scale_y = start["scale_y"] * (new_half / orig_half)

        # Redraw overlay
        self._draw_transform_overlay()
        self._update_transform_context_display()

    def _transform_handle_release(self, x, y, event_state=0):
        """Handle mouse release during selection transform mode."""
        t = self._selection_transform
        zone = getattr(self, '_transform_drag_zone', None)

        if zone == "outside" and bool(event_state & 0x0001):
            # Shift held on rotation release → snap to 15°
            t.rotation = round(t.rotation / 15) * 15
            self._draw_transform_overlay()
            self._update_transform_context_display()

        self._transform_drag_zone = None
        self.pixel_canvas.config(cursor="arrow")
```

- [ ] **Step 2: Add missing imports at top of input_handler.py**

Add these imports at the top of `src/input_handler.py` (check which are already present):

```python
import math
import tkinter as tk
```

Both are needed: `math` for angle/distance calculations in drag handlers, `tk` for the context bar widgets in Task 9.

- [ ] **Step 3: Track Ctrl and Shift key state**

Add to `_transform_handle_click`, after `self._transform_start_state = {...}`:

```python
        self._transform_ctrl_held = bool(event_state & 0x0004)
        self._transform_shift_held = bool(event_state & 0x0001)
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/input_handler.py
git commit -m "feat: add transform drag handlers for scale, rotate, move, skew, pivot"
```

---

## Task 9: Context Bar

**Files:**
- Modify: `src/input_handler.py`

- [ ] **Step 1: Implement the transform context bar**

Add to `InputHandlerMixin` in `src/input_handler.py`:

```python
    def _show_transform_context_bar(self):
        """Show context bar with angle, scale, apply/cancel buttons."""
        self._hide_transform_context_bar()

        from src.ui.theme import (
            ACCENT_CYAN, BG_DEEP, BG_PANEL, BG_PANEL_ALT,
            BUTTON_BG, BUTTON_HOVER, TEXT_PRIMARY, TEXT_SECONDARY,
        )

        frame = tk.Frame(self.options_bar, bg=BG_PANEL)
        frame.pack(side="right", padx=4)
        self._transform_context_frame = frame

        # "Transform" label
        tk.Label(frame, text="Transform", fg=ACCENT_CYAN, bg=BG_PANEL,
                 font=("Consolas", 8, "bold")).pack(side="left", padx=(4, 8))

        # Angle
        tk.Label(frame, text="Angle:", fg=TEXT_SECONDARY, bg=BG_PANEL,
                 font=("Consolas", 8)).pack(side="left", padx=(0, 2))
        self._transform_angle_var = tk.StringVar(value="0.0")
        angle_entry = tk.Entry(frame, textvariable=self._transform_angle_var,
                               width=6, bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                               font=("Consolas", 8), insertbackground=TEXT_PRIMARY)
        angle_entry.pack(side="left", padx=2)
        angle_entry.bind("<Return>", self._on_transform_angle_entry)
        tk.Label(frame, text="°", fg=TEXT_SECONDARY, bg=BG_PANEL,
                 font=("Consolas", 8)).pack(side="left")

        # Scale
        tk.Label(frame, text="Scale:", fg=TEXT_SECONDARY, bg=BG_PANEL,
                 font=("Consolas", 8)).pack(side="left", padx=(8, 2))
        self._transform_scale_var = tk.StringVar(value="100")
        scale_entry = tk.Entry(frame, textvariable=self._transform_scale_var,
                               width=5, bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                               font=("Consolas", 8), insertbackground=TEXT_PRIMARY)
        scale_entry.pack(side="left", padx=2)
        scale_entry.bind("<Return>", self._on_transform_scale_entry)
        tk.Label(frame, text="%", fg=TEXT_SECONDARY, bg=BG_PANEL,
                 font=("Consolas", 8)).pack(side="left")

        # Apply button
        tk.Button(frame, text="Apply", bg=ACCENT_CYAN, fg=BG_DEEP,
                  font=("Consolas", 8, "bold"), relief="flat",
                  activebackground=BUTTON_HOVER,
                  command=self._commit_selection_transform
                  ).pack(side="left", padx=(8, 2))

        # Cancel button
        tk.Button(frame, text="Cancel", bg=BUTTON_BG, fg=TEXT_PRIMARY,
                  font=("Consolas", 8), relief="flat",
                  activebackground=BUTTON_HOVER,
                  command=self._cancel_selection_transform
                  ).pack(side="left", padx=2)

    def _hide_transform_context_bar(self):
        """Remove the transform context bar."""
        frame = getattr(self, '_transform_context_frame', None)
        if frame is not None:
            frame.destroy()
            self._transform_context_frame = None

    def _update_transform_context_display(self):
        """Update angle and scale displays in the context bar."""
        t = self._selection_transform
        if t is None:
            return
        if hasattr(self, '_transform_angle_var'):
            self._transform_angle_var.set(f"{t.rotation:.1f}")
        if hasattr(self, '_transform_scale_var'):
            avg_scale = (t.scale_x + t.scale_y) / 2.0
            self._transform_scale_var.set(f"{avg_scale * 100:.0f}")

    def _on_transform_angle_entry(self, event=None):
        """Handle manual angle entry in context bar."""
        try:
            angle = float(self._transform_angle_var.get())
            self._selection_transform.rotation = angle
            self._draw_transform_overlay()
        except (ValueError, AttributeError):
            pass

    def _on_transform_scale_entry(self, event=None):
        """Handle manual scale entry in context bar."""
        try:
            pct = float(self._transform_scale_var.get())
            factor = pct / 100.0
            if factor > 0:
                self._selection_transform.scale_x = factor
                self._selection_transform.scale_y = factor
                self._draw_transform_overlay()
        except (ValueError, AttributeError):
            pass
```

- [ ] **Step 2: Auto-commit transform on tool switch**

In `src/app.py`, find `_on_tool_change` (around line 646). At the top of the method, add:

```python
        # Commit any active selection transform before switching tools
        if self._selection_transform is not None:
            self._commit_selection_transform()
```

This handles the spec requirement: "Commit on switch tools".

- [ ] **Step 3: Run all tests**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add src/input_handler.py src/app.py
git commit -m "feat: add selection transform context bar with angle/scale entry"
```

---

## Task 10: Cursor Feedback

**Files:**
- Modify: `src/input_handler.py` (the motion handler)

- [ ] **Step 1: Add cursor updating on hover during transform mode**

In `_on_canvas_motion` (around line 413), add transform mode hover before the paste check:

```python
        # Transform mode cursor feedback
        if self._selection_transform is not None:
            from src.selection_transform import hit_test_transform_handle
            hit = hit_test_transform_handle(
                self._selection_transform, x, y, self.pixel_canvas.pixel_size)
            cursors = {
                "inside": "fleur", "outside": "exchange", "pivot": "crosshair",
            }
            if hit and hit.startswith("corner:"):
                self.pixel_canvas.config(cursor="sizing")
            elif hit and hit.startswith("midpoint:"):
                if "top" in hit or "bottom" in hit:
                    self.pixel_canvas.config(cursor="sb_v_double_arrow")
                else:
                    self.pixel_canvas.config(cursor="sb_h_double_arrow")
            elif hit in cursors:
                self.pixel_canvas.config(cursor=cursors[hit])
            else:
                self.pixel_canvas.config(cursor="arrow")
            return
```

- [ ] **Step 2: Run all tests**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add src/input_handler.py
git commit -m "feat: add cursor feedback for transform handle zones"
```

---

## Task 11: Final Integration Test

**Files:**
- Modify: `tests/test_selection_transform.py`

- [ ] **Step 1: Write integration test for full transform flow**

```python
# Add to tests/test_selection_transform.py

class TestCommitUndo:
    def test_commit_pushes_result_to_grid(self):
        """Full flow: create transform, scale 2x, commit, verify pixels."""
        from src.pixel_data import PixelGrid
        from src.selection_transform import (
            SelectionTransform, compute_affine_final,
            get_transform_bounding_box, clip_to_canvas,
        )

        img = _make_test_image(4, 4, color=(0, 0, 255, 255))
        t = SelectionTransform(pixels=img, position=(2, 2), scale_x=2.0, scale_y=2.0)

        final = compute_affine_final(t)
        corners = get_transform_bounding_box(t)
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        place_x, place_y = int(min(xs)), int(min(ys))

        grid = PixelGrid(16, 16)
        clip_to_canvas(final, (place_x, place_y), grid)

        # The center region should have blue pixels
        center = grid.get_pixel(4, 4)
        assert center[2] == 255  # Blue channel
        assert center[3] == 255  # Fully opaque

    def test_cancel_float_restores_pixels(self):
        """Cancel after floating should restore original pixels."""
        from src.pixel_data import PixelGrid
        from src.selection_transform import SelectionTransform, clip_to_canvas

        img = _make_test_image(3, 3, color=(255, 255, 0, 255))
        t = SelectionTransform(pixels=img, position=(1, 1), source="float")

        # Simulate cancel: paste original back
        grid = PixelGrid(8, 8)
        clip_to_canvas(t.pixels, t.position, grid)

        assert tuple(grid.get_pixel(1, 1)) == (255, 255, 0, 255)
        assert tuple(grid.get_pixel(3, 3)) == (255, 255, 0, 255)
```

- [ ] **Step 2: Run all tests**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 3: Run the full test suite one final time**

Run: `python -m pytest tests/ -v`
Expected: All tests pass including the new `test_selection_transform.py`

- [ ] **Step 4: Commit**

```bash
git add tests/test_selection_transform.py
git commit -m "test: add integration tests for transform commit and cancel flows"
```

---

## Summary

| Task | What it builds | Tests |
|------|---------------|-------|
| 1 | `SelectionTransform` dataclass + identity preview | 3 |
| 2 | Affine preview (rotation, scale, skew) | 6 |
| 3 | `compute_affine_final` with RotSprite | 3 |
| 4 | Bounding box + hit testing | 10 |
| 5 | Canvas handle drawing | 1 |
| 6 | App state + Ctrl+T binding | 0 (integration) |
| 7 | Enter/commit/cancel + event routing | 2 |
| 8 | Drag handlers (all zones) | 0 (manual test) |
| 9 | Context bar | 0 (UI) |
| 10 | Cursor feedback | 0 (UI) |
| 11 | Integration tests | 2 |
| **Total** | | **~27 tests** |
