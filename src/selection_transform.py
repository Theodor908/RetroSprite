"""Selection transform: affine math, preview, hit testing."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from src.pixel_data import PixelGrid



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

    # Forward angle for computing output bounds (matches get_transform_bounding_box)
    fwd_rad = math.radians(transform.rotation)
    fwd_cos = math.cos(fwd_rad)
    fwd_sin = math.sin(fwd_rad)

    sx = transform.scale_x if transform.scale_x != 0 else 0.001
    sy = transform.scale_y if transform.scale_y != 0 else 0.001

    skx = math.tan(math.radians(transform.skew_x))
    sky = math.tan(math.radians(transform.skew_y))

    # New dimensions to fit the transformed content
    corners = [(0, 0), (w, 0), (w, h), (0, h)]
    transformed = []
    for cx, cy in corners:
        dx, dy = cx - px, cy - py
        # Skew
        dx, dy = dx + skx * dy, dy + sky * dx
        # Scale
        dx, dy = dx * sx, dy * sy
        # Rotate (forward)
        rx = dx * fwd_cos - dy * fwd_sin
        ry = dx * fwd_sin + dy * fwd_cos
        transformed.append((rx + px, ry + py))

    xs = [p[0] for p in transformed]
    ys = [p[1] for p in transformed]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    out_w = max(1, int(math.ceil(max_x - min_x)))
    out_h = max(1, int(math.ceil(max_y - min_y)))

    # Inverse angle for Pillow's output-to-input mapping
    inv_rad = -fwd_rad
    inv_cos = math.cos(inv_rad)
    inv_sin = math.sin(inv_rad)

    def _inv_transform(ox, oy):
        cx = ox + min_x
        cy = oy + min_y
        dx = cx - px
        dy = cy - py
        rx = dx * inv_cos - dy * inv_sin
        ry = dx * inv_sin + dy * inv_cos
        rx = rx / sx
        ry = ry / sy
        det = 1.0 - skx * sky
        if abs(det) < 1e-10:
            det = 1e-10
        ix = (rx - skx * ry) / det
        iy = (ry - sky * rx) / det
        return ix + px, iy + py

    x00, y00 = _inv_transform(0, 0)
    x10, y10 = _inv_transform(1, 0)
    x01, y01 = _inv_transform(0, 1)

    a = x10 - x00
    b = x01 - x00
    c = x00
    d = y10 - y00
    e = y01 - y00
    f = y00

    result = src.transform(
        (out_w, out_h), Image.AFFINE,
        (a, b, c, d, e, f),
        resample=Image.NEAREST,
        fillcolor=(0, 0, 0, 0),
    )
    return result


def get_transform_bounding_box(transform: SelectionTransform) -> list[tuple[float, float]]:
    """Return 4 corners of the transformed bounding box in canvas coordinates.

    Returns: [(x,y), (x,y), (x,y), (x,y)] — TL, TR, BR, BL order.
    """
    w, h = transform.pixels.size
    ox, oy = transform.position
    px, py = transform.pivot

    local_corners = [(0, 0), (w, 0), (w, h), (0, h)]

    rad = math.radians(transform.rotation)
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)
    skx = math.tan(math.radians(transform.skew_x))
    sky = math.tan(math.radians(transform.skew_y))

    result = []
    for lx, ly in local_corners:
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
                               threshold: float = 2.5) -> str | None:
    """Test what zone a canvas coordinate hits.

    Args:
        transform: Active SelectionTransform
        canvas_x, canvas_y: Position in canvas coordinates (grid pixels)
        pixel_size: Zoom level (screen pixels per grid pixel)
        threshold: Hit distance in canvas pixels

    Returns: "corner:0"-"corner:3", "midpoint:top/right/bottom/left",
             "pivot", "inside", "outside"
    """
    corners = get_transform_bounding_box(transform)
    ox, oy = transform.position
    px, py = transform.pivot

    pivot_cx = px + ox
    pivot_cy = py + oy

    midpoints = {
        "top": ((corners[0][0] + corners[1][0]) / 2, (corners[0][1] + corners[1][1]) / 2),
        "right": ((corners[1][0] + corners[2][0]) / 2, (corners[1][1] + corners[2][1]) / 2),
        "bottom": ((corners[2][0] + corners[3][0]) / 2, (corners[2][1] + corners[3][1]) / 2),
        "left": ((corners[3][0] + corners[0][0]) / 2, (corners[3][1] + corners[0][1]) / 2),
    }

    # Collect all candidate handles and pick the nearest within threshold
    candidates: list[tuple[float, str]] = []

    for i, (cx, cy) in enumerate(corners):
        d = math.hypot(canvas_x - cx, canvas_y - cy)
        if d <= threshold:
            candidates.append((d, f"corner:{i}"))

    for name, (mx, my) in midpoints.items():
        d = math.hypot(canvas_x - mx, canvas_y - my)
        if d <= threshold:
            candidates.append((d, f"midpoint:{name}"))

    d_pivot = math.hypot(canvas_x - pivot_cx, canvas_y - pivot_cy)
    if d_pivot <= threshold:
        candidates.append((d_pivot, "pivot"))

    if candidates:
        candidates.sort(key=lambda c: c[0])
        return candidates[0][1]

    # 4. Check inside bounding box (cross-product point-in-polygon)
    def _cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    point = (canvas_x, canvas_y)
    signs = []
    for i in range(4):
        cp = _cross(corners[i], corners[(i + 1) % 4], point)
        signs.append(cp >= 0)
    if all(signs) or not any(signs):
        return "inside"

    # 5. Everything else
    return "outside"


def compute_affine_final(transform: SelectionTransform) -> Image.Image:
    """Final render using the same single-pass AFFINE as the preview.

    Uses nearest-neighbor resampling which preserves pixel art crispness
    and ensures the commit matches what the user sees during preview.
    """
    return compute_affine_preview(transform)


def clip_to_canvas(image: Image.Image, position: tuple[int, int],
                   target: PixelGrid) -> None:
    """Paste an RGBA image onto a PixelGrid, clipping to canvas bounds.

    Only non-transparent pixels are pasted. Delegates to
    PixelGrid.paste_rgba_array for vectorized NumPy ops.
    """
    arr = np.array(image)
    ox, oy = position
    target.paste_rgba_array(arr, ox, oy)
