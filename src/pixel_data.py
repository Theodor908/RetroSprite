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

    def paste_rgba_array(self, arr: np.ndarray, x: int, y: int) -> None:
        """Paste an (H, W, 4) uint8 RGBA array at (x, y), clipping to bounds.

        Only non-transparent pixels are written. Uses vectorized NumPy ops.
        """
        ih, iw = arr.shape[:2]
        src_x0 = max(0, -x)
        src_y0 = max(0, -y)
        src_x1 = min(iw, self.width - x)
        src_y1 = min(ih, self.height - y)
        if src_x0 >= src_x1 or src_y0 >= src_y1:
            return
        region = arr[src_y0:src_y1, src_x0:src_x1]
        dst = self._pixels[y + src_y0:y + src_y0 + region.shape[0],
                           x + src_x0:x + src_x0 + region.shape[1]]
        mask = region[:, :, 3] > 0
        dst[mask] = region[mask]


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
