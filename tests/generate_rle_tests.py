"""Generate .rle test files to exercise RLE compression with various patterns.

Run:  python -m tests.generate_rle_tests
Creates files in tests/rle_samples/
"""
from __future__ import annotations
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.pixel_data import PixelGrid
from src.compression import compress_grid, save_rle

OUT_DIR = os.path.join(os.path.dirname(__file__), "rle_samples")


def _save(name: str, grid: PixelGrid):
    encoded, stats = compress_grid(grid)
    path = os.path.join(OUT_DIR, f"{name}.rle")
    save_rle(encoded, grid.width, grid.height, path)
    ratio = stats["ratio"]
    runs = stats["run_count"]
    pixels = stats["pixel_count"]
    print(f"  {name:30s}  {grid.width:3d}x{grid.height:<3d}  "
          f"{pixels:5d} px  {runs:4d} runs  {ratio:5.1f}x ratio")


# --------------- Pattern generators ---------------

def solid_fill(w, h, color):
    """Best-case: one solid color → minimal runs."""
    g = PixelGrid(w, h)
    for y in range(h):
        for x in range(w):
            g.set_pixel(x, y, color)
    return g


def checkerboard(w, h, c1, c2):
    """Worst-case: alternating pixels → no compression."""
    g = PixelGrid(w, h)
    for y in range(h):
        for x in range(w):
            g.set_pixel(x, y, c1 if (x + y) % 2 == 0 else c2)
    return g


def horizontal_stripes(w, h, colors):
    """Good compression: each row is one color run."""
    g = PixelGrid(w, h)
    for y in range(h):
        c = colors[y % len(colors)]
        for x in range(w):
            g.set_pixel(x, y, c)
    return g


def vertical_stripes(w, h, colors):
    """Poor compression in row-major: every pixel alternates."""
    g = PixelGrid(w, h)
    for y in range(h):
        for x in range(w):
            g.set_pixel(x, y, colors[x % len(colors)])
    return g


def gradient_horizontal(w, h):
    """Each pixel unique along x → no runs."""
    g = PixelGrid(w, h)
    for y in range(h):
        for x in range(w):
            v = int(255 * x / max(w - 1, 1))
            g.set_pixel(x, y, (v, v, v, 255))
    return g


def gradient_vertical(w, h):
    """Each row same → great compression."""
    g = PixelGrid(w, h)
    for y in range(h):
        v = int(255 * y / max(h - 1, 1))
        for x in range(w):
            g.set_pixel(x, y, (v, v, v, 255))
    return g


def sparse_dots(w, h, dot_color, spacing=4):
    """Mostly transparent with occasional dots."""
    g = PixelGrid(w, h)
    for y in range(0, h, spacing):
        for x in range(0, w, spacing):
            g.set_pixel(x, y, dot_color)
    return g


def border_only(w, h, color):
    """Only edges filled — moderate compression."""
    g = PixelGrid(w, h)
    for x in range(w):
        g.set_pixel(x, 0, color)
        g.set_pixel(x, h - 1, color)
    for y in range(h):
        g.set_pixel(0, y, color)
        g.set_pixel(w - 1, y, color)
    return g


def diagonal_lines(w, h, color):
    """Diagonal pattern — tests run fragmentation."""
    g = PixelGrid(w, h)
    for y in range(h):
        for x in range(w):
            if (x + y) % 8 == 0:
                g.set_pixel(x, y, color)
    return g


def smiley_face(size=16):
    """Small sprite — realistic pixel art test."""
    g = PixelGrid(size, size)
    yellow = (255, 220, 50, 255)
    black = (0, 0, 0, 255)
    # Face circle (rough)
    cx, cy, r = size // 2, size // 2, size // 2 - 1
    for y in range(size):
        for x in range(size):
            dx, dy = x - cx, y - cy
            if dx * dx + dy * dy <= r * r:
                g.set_pixel(x, y, yellow)
    # Eyes
    g.set_pixel(cx - 3, cy - 2, black)
    g.set_pixel(cx + 3, cy - 2, black)
    # Mouth
    for x in range(cx - 3, cx + 4):
        g.set_pixel(x, cy + 3, black)
    g.set_pixel(cx - 4, cy + 2, black)
    g.set_pixel(cx + 4, cy + 2, black)
    return g


def noise_block(w, h):
    """Random-ish pattern using deterministic formula — worst case."""
    g = PixelGrid(w, h)
    for y in range(h):
        for x in range(w):
            v = ((x * 137 + y * 251 + 97) % 256)
            g.set_pixel(x, y, (v, (v * 3) % 256, (v * 7) % 256, 255))
    return g


# --------------- Main ---------------

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    RED = (255, 0, 0, 255)
    GREEN = (0, 200, 0, 255)
    BLUE = (0, 100, 255, 255)
    WHITE = (255, 255, 255, 255)
    BLACK = (0, 0, 0, 255)
    TRANS = (0, 0, 0, 0)

    print("Generating RLE test samples…")
    print(f"{'Name':34s} {'Size':8s} {'Pixels':>7s} {'Runs':>6s} {'Ratio':>7s}")
    print("-" * 68)

    # Best-case compression
    _save("solid_red_64x64", solid_fill(64, 64, RED))
    _save("solid_transparent_128x128", solid_fill(128, 128, TRANS))

    # Stripe patterns (good vs poor row-major compression)
    _save("h_stripes_64x64", horizontal_stripes(64, 64, [RED, BLUE, GREEN]))
    _save("v_stripes_64x64", vertical_stripes(64, 64, [RED, BLUE, GREEN]))

    # Gradients
    _save("grad_horiz_64x64", gradient_horizontal(64, 64))
    _save("grad_vert_64x64", gradient_vertical(64, 64))

    # Patterns
    _save("checkerboard_32x32", checkerboard(32, 32, BLACK, WHITE))
    _save("sparse_dots_64x64", sparse_dots(64, 64, RED, spacing=4))
    _save("border_64x64", border_only(64, 64, BLUE))
    _save("diagonal_64x64", diagonal_lines(64, 64, GREEN))

    # Realistic sprite
    _save("smiley_16x16", smiley_face(16))

    # Stress tests
    _save("noise_32x32", noise_block(32, 32))
    _save("solid_large_256x256", solid_fill(256, 256, WHITE))
    _save("checker_large_128x128", checkerboard(128, 128, RED, BLUE))

    # Tiny edge case
    _save("single_pixel_1x1", solid_fill(1, 1, RED))
    _save("one_row_128x1", solid_fill(128, 1, GREEN))
    _save("one_col_1x128", solid_fill(1, 128, BLUE))

    print(f"\n{len(os.listdir(OUT_DIR))} files saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
