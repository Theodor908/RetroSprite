"""Color reduction via median cut algorithm."""
from __future__ import annotations
import numpy as np
from src.pixel_data import PixelGrid, IndexedPixelGrid, nearest_palette_index


def median_cut(pixels: np.ndarray, num_colors: int) -> list[tuple[int, int, int, int]]:
    """Pick a representative palette by recursively splitting color space."""
    num_colors = max(1, min(256, num_colors))
    opaque = pixels[pixels[:, 3] > 0]
    if len(opaque) == 0:
        return [(0, 0, 0, 255)] * num_colors

    rgb = opaque[:, :3].astype(np.int32)

    boxes = [rgb]
    while len(boxes) < num_colors:
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
