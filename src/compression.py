"""RLE compression for pixel data."""
from __future__ import annotations
import json
from src.pixel_data import PixelGrid


def rle_encode(data: list[tuple]) -> list[tuple[int, tuple]]:
    """Collapse consecutive identical pixels into (count, pixel) pairs."""
    if not data:
        return []
    encoded = []
    current = data[0]
    count = 1
    for pixel in data[1:]:
        if pixel == current:
            count += 1
        else:
            encoded.append((count, current))
            current = pixel
            count = 1
    encoded.append((count, current))
    return encoded


def rle_decode(encoded: list[tuple[int, tuple]]) -> list[tuple]:
    """Expand (count, pixel) pairs back into a flat pixel list."""
    result = []
    for count, value in encoded:
        result.extend([value] * count)
    return result


def compress_grid(grid: PixelGrid) -> tuple[list[tuple[int, tuple]], dict]:
    """RLE-compress a grid. Returns (encoded_runs, stats)."""
    flat = grid.to_flat_list()
    encoded = rle_encode(flat)
    original_size = len(flat) * 4  # 4 bytes per RGBA pixel
    compressed_size = len(encoded) * 5  # count(1) + RGBA(4)
    ratio = original_size / compressed_size if compressed_size > 0 else 0
    stats = {
        "original_size": original_size,
        "compressed_size": compressed_size,
        "ratio": round(ratio, 2),
        "run_count": len(encoded),
        "pixel_count": len(flat),
    }
    return encoded, stats


def decompress_grid(encoded: list[tuple[int, tuple]], width: int, height: int) -> PixelGrid:
    """Rebuild a PixelGrid from RLE-encoded runs."""
    flat = rle_decode(encoded)
    grid = PixelGrid(width, height)
    for i, pixel in enumerate(flat):
        x = i % width
        y = i // width
        if y < height:
            grid.set_pixel(x, y, pixel)
    return grid


def save_rle(encoded: list, width: int, height: int, filepath: str) -> None:
    """Write RLE data to a JSON file."""
    data = {
        "format": "retrosprite-rle",
        "version": 1,
        "width": width,
        "height": height,
        "runs": [[count, list(color)] for count, color in encoded],
    }
    with open(filepath, "w") as f:
        json.dump(data, f)


def load_rle(filepath: str) -> tuple[list[tuple[int, tuple]], int, int]:
    """Read RLE data from a JSON file. Returns (runs, width, height)."""
    with open(filepath, "r") as f:
        data = json.load(f)
    encoded = [(run[0], tuple(run[1])) for run in data["runs"]]
    return encoded, data["width"], data["height"]
