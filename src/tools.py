"""Drawing tools for the pixel canvas."""
from __future__ import annotations
from collections import deque
from src.pixel_data import PixelGrid
from PIL import Image


DITHER_PATTERNS = {
    "none": None,
    "checker": [[1, 0], [0, 1]],
    "25%": [[1, 0, 0, 0], [0, 0, 0, 0], [0, 0, 1, 0], [0, 0, 0, 0]],
    "50%": [[1, 0], [0, 1]],
    "75%": [[1, 1], [1, 0]],
}


def _set_thick(grid: PixelGrid, x: int, y: int, color: tuple, width: int = 1) -> None:
    """Set a square of pixels centered on (x, y) with given width."""
    if width <= 1:
        grid.set_pixel(x, y, color)
        return
    half = width // 2
    for dy in range(-half, -half + width):
        for dx in range(-half, -half + width):
            grid.set_pixel(x + dx, y + dy, color)


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


class BlurTool:
    """3×3 box blur applied within the brush footprint.

    Each pixel under the brush is replaced by a weighted average of its
    3×3 neighborhood (including itself), then blended back with the
    original at the given strength.  Fully transparent neighbors are
    excluded from the average to prevent dark-halo artifacts at edges.
    Fully transparent pixels are never modified.
    """

    def __init__(self, strength: float = 0.3):
        self.strength = strength

    def apply(self, grid: PixelGrid, x: int, y: int,
              size: int = 3) -> None:
        half = size // 2

        # Snapshot every pixel we might read (brush footprint + 1px border)
        originals: dict[tuple[int, int], tuple[int, int, int, int]] = {}
        for dy in range(-half - 1, -half + size + 1):
            for dx in range(-half - 1, -half + size + 1):
                gx, gy = x + dx, y + dy
                pixel = grid.get_pixel(gx, gy)
                if pixel is not None:
                    originals[(gx, gy)] = pixel

        changes: dict[tuple[int, int], tuple[int, int, int, int]] = {}

        for dy in range(size):
            for dx in range(size):
                gx = x - half + dx
                gy = y - half + dy
                pixel = originals.get((gx, gy))
                if pixel is None:
                    continue
                r, g, b, a = pixel

                # Skip fully transparent pixels — nothing to blur
                if a == 0:
                    continue

                # 3×3 box average
                # RGB: only among opaque neighbors (prevents dark halo)
                # Alpha: among ALL neighbors (allows soft edge falloff)
                total_r = total_g = total_b = 0.0
                total_a = 0.0
                rgb_count = 0
                all_count = 0
                for ny in range(-1, 2):
                    for nx in range(-1, 2):
                        nb = originals.get((gx + nx, gy + ny))
                        if nb is not None:
                            total_a += nb[3]
                            all_count += 1
                            if nb[3] > 0:
                                total_r += nb[0]
                                total_g += nb[1]
                                total_b += nb[2]
                                rgb_count += 1
                        else:
                            # Out-of-bounds counts as transparent for alpha
                            all_count += 1

                if rgb_count == 0:
                    continue

                avg_r = total_r / rgb_count
                avg_g = total_g / rgb_count
                avg_b = total_b / rgb_count
                avg_a = total_a / all_count

                # Blend original toward average by strength
                new_r = int(r + (avg_r - r) * self.strength + 0.5)
                new_g = int(g + (avg_g - g) * self.strength + 0.5)
                new_b = int(b + (avg_b - b) * self.strength + 0.5)
                new_a = int(a + (avg_a - a) * self.strength + 0.5)

                new_r = max(0, min(255, new_r))
                new_g = max(0, min(255, new_g))
                new_b = max(0, min(255, new_b))
                new_a = max(0, min(255, new_a))

                changes[(gx, gy)] = (new_r, new_g, new_b, new_a)

        for (gx, gy), color in changes.items():
            grid.set_pixel(gx, gy, color)


class FillTool:
    @staticmethod
    def apply(grid: PixelGrid, x: int, y: int, color: tuple, contour: bool = False) -> None:
        if x < 0 or x >= grid.width or y < 0 or y >= grid.height:
            return
        target = grid.get_pixel(x, y)
        if target is None or target == color:
            return
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
            for px, py in region:
                grid.set_pixel(px, py, color)


class LineTool:
    def apply(self, grid: PixelGrid, x0: int, y0: int, x1: int, y1: int,
              color: tuple, width: int = 1) -> None:
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            _set_thick(grid, x0, y0, color, width)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy


class RectTool:
    def apply(self, grid: PixelGrid, x0: int, y0: int, x1: int, y1: int,
              color: tuple, filled: bool = False, width: int = 1) -> None:
        min_x, max_x = min(x0, x1), max(x0, x1)
        min_y, max_y = min(y0, y1), max(y0, y1)
        if filled:
            for y in range(min_y, max_y + 1):
                for x in range(min_x, max_x + 1):
                    grid.set_pixel(x, y, color)
        else:
            for x in range(min_x, max_x + 1):
                _set_thick(grid, x, min_y, color, width)
                _set_thick(grid, x, max_y, color, width)
            for y in range(min_y, max_y + 1):
                _set_thick(grid, min_x, y, color, width)
                _set_thick(grid, max_x, y, color, width)


class EllipseTool:
    def apply(self, grid: PixelGrid, x0: int, y0: int, x1: int, y1: int,
              color: tuple, filled: bool = False, width: int = 1) -> None:
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        rx = abs(x1 - x0) // 2
        ry = abs(y1 - y0) // 2
        if rx == 0 or ry == 0:
            return
        self._width = width
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
        w = getattr(self, '_width', 1)
        _set_thick(grid, cx + x, cy + y, color, w)
        _set_thick(grid, cx - x, cy + y, color, w)
        _set_thick(grid, cx + x, cy - y, color, w)
        _set_thick(grid, cx - x, cy - y, color, w)

    def _fill_line(self, grid, x0, x1, y, color):
        for x in range(x0, x1 + 1):
            grid.set_pixel(x, y, color)


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
            _polygon_scanfill(grid, points, color)
        else:
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
            t = (y - y0) / (y1 - y0)
            ix = x0 + t * (x1 - x0)
            intersections.append(ix)

        intersections.sort()
        for j in range(0, len(intersections) - 1, 2):
            x_start = max(0, int(intersections[j] + 0.5))
            x_end = min(grid.width - 1, int(intersections[j + 1] + 0.5))
            for x in range(x_start, x_end + 1):
                grid.set_pixel(x, y, color)


class RoundedRectTool:
    """Draw rectangles with rounded corners."""

    @staticmethod
    def apply(grid, x0: int, y0: int, x1: int, y1: int, color: tuple,
              radius: int = 2, filled: bool = False, width: int = 1) -> None:
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        w = x1 - x0
        h = y1 - y0
        max_r = max(0, min(w, h) // 2 - 1)
        r = min(radius, max_r)
        if r <= 0:
            RectTool().apply(grid, x0, y0, x1, y1, color, filled=filled, width=width)
            return
        if filled:
            _rounded_rect_filled(grid, x0, y0, x1, y1, r, color)
        else:
            _rounded_rect_outline(grid, x0, y0, x1, y1, r, color, width)


def _rounded_rect_outline(grid, x0, y0, x1, y1, r, color, width):
    line = LineTool()
    line.apply(grid, x0 + r, y0, x1 - r, y0, color, width=width)
    line.apply(grid, x0 + r, y1, x1 - r, y1, color, width=width)
    line.apply(grid, x0, y0 + r, x0, y1 - r, color, width=width)
    line.apply(grid, x1, y0 + r, x1, y1 - r, color, width=width)
    _quarter_circle(grid, x0 + r, y0 + r, r, color, "tl", width)
    _quarter_circle(grid, x1 - r, y0 + r, r, color, "tr", width)
    _quarter_circle(grid, x0 + r, y1 - r, r, color, "bl", width)
    _quarter_circle(grid, x1 - r, y1 - r, r, color, "br", width)


def _rounded_rect_filled(grid, x0, y0, x1, y1, r, color):
    for y in range(y0, y1 + 1):
        if y < y0 + r:
            dy = y0 + r - y
            dx = int((r * r - dy * dy) ** 0.5 + 0.5)
            xl = x0 + r - dx
            xr = x1 - r + dx
        elif y > y1 - r:
            dy = y - (y1 - r)
            dx = int((r * r - dy * dy) ** 0.5 + 0.5)
            xl = x0 + r - dx
            xr = x1 - r + dx
        else:
            xl = x0
            xr = x1
        xl = max(0, xl)
        xr = min(grid.width - 1, xr)
        for x in range(xl, xr + 1):
            if 0 <= y < grid.height:
                grid.set_pixel(x, y, color)


def _quarter_circle(grid, cx, cy, r, color, quadrant, width=1):
    x, y = 0, r
    d = 1 - r
    while x <= y:
        if quadrant == "tl":
            points = [(-y, -x), (-x, -y)]
        elif quadrant == "tr":
            points = [(y, -x), (x, -y)]
        elif quadrant == "bl":
            points = [(-y, x), (-x, y)]
        elif quadrant == "br":
            points = [(y, x), (x, y)]
        for ddx, ddy in points:
            px, py = cx + ddx, cy + ddy
            if 0 <= px < grid.width and 0 <= py < grid.height:
                _set_thick(grid, px, py, color, width)
        if d < 0:
            d += 2 * x + 3
        else:
            d += 2 * (x - y) + 5
            y -= 1
        x += 1


class MagicWandTool:
    def apply(self, grid: PixelGrid, x: int, y: int, tolerance: int = 0) -> set:
        target = grid.get_pixel(x, y)
        if target is None:
            return set()
        selected = set()
        queue = deque([(x, y)])
        while queue:
            cx, cy = queue.popleft()
            if (cx, cy) in selected:
                continue
            if not (0 <= cx < grid.width and 0 <= cy < grid.height):
                continue
            pixel = grid.get_pixel(cx, cy)
            if self._color_distance(pixel, target) > tolerance:
                continue
            selected.add((cx, cy))
            queue.extend([(cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)])
        return selected

    def _color_distance(self, c1, c2):
        return max(abs(a - b) for a, b in zip(c1, c2))


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


class ShadingInkTool:
    def apply(self, grid: PixelGrid, x: int, y: int, palette: list,
              mode: str = "lighten") -> None:
        pixel = grid.get_pixel(x, y)
        if pixel is None or pixel[3] == 0:
            return
        # Sort palette by luminance
        sorted_pal = sorted(palette,
                            key=lambda c: 0.299*c[0] + 0.587*c[1] + 0.114*c[2])
        # Find closest palette color
        best_idx = 0
        best_dist = float('inf')
        for i, c in enumerate(sorted_pal):
            dist = sum(abs(a-b) for a, b in zip(pixel[:3], c[:3]))
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        # Shift
        if mode == "lighten" and best_idx < len(sorted_pal) - 1:
            grid.set_pixel(x, y, sorted_pal[best_idx + 1])
        elif mode == "darken" and best_idx > 0:
            grid.set_pixel(x, y, sorted_pal[best_idx - 1])


class GradientFillTool:
    BAYER_4X4 = [
        [0, 8, 2, 10],
        [12, 4, 14, 6],
        [3, 11, 1, 9],
        [15, 7, 13, 5],
    ]

    def apply(self, grid: PixelGrid, x0: int, y0: int, x1: int, y1: int,
              color1: tuple, color2: tuple) -> None:
        dx = x1 - x0
        dy = y1 - y0
        length = max(abs(dx), abs(dy), 1)
        for y in range(grid.height):
            for x in range(grid.width):
                # Project pixel onto gradient vector
                t = ((x - x0) * dx + (y - y0) * dy) / (length * length)
                t = max(0.0, min(1.0, t))
                # Bayer dithering threshold
                threshold = self.BAYER_4X4[y % 4][x % 4] / 16.0
                # Choose color based on t vs threshold
                if t < threshold:
                    color = color1
                else:
                    color = color2
                grid.set_pixel(x, y, color)


class TextTool:
    """Stamp a rendered text image onto a PixelGrid."""

    def apply(self, grid: PixelGrid, image: Image.Image, x: int, y: int) -> None:
        """Paste text image onto grid at (x, y), clipping to bounds."""
        import numpy as np
        arr = np.array(image)
        grid.paste_rgba_array(arr, x, y)
