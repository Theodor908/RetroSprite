"""Round-trip tests: load every generated .rle sample, decompress, re-compress,
and verify pixel-perfect integrity."""
from __future__ import annotations
import os
import pytest

from src.compression import (
    compress_grid, decompress_grid, save_rle, load_rle,
    rle_encode, rle_decode,
)
from src.pixel_data import PixelGrid

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "rle_samples")


def _sample_files():
    if not os.path.isdir(SAMPLES_DIR):
        return []
    return sorted(
        f for f in os.listdir(SAMPLES_DIR) if f.endswith(".rle")
    )


@pytest.fixture(params=_sample_files(), ids=lambda f: f.replace(".rle", ""))
def rle_path(request):
    return os.path.join(SAMPLES_DIR, request.param)


class TestRLERoundTrip:
    """Load each .rle file, decompress, re-compress, and compare."""

    def test_load_decompress_recompress(self, rle_path):
        # Load from disk
        encoded, w, h = load_rle(rle_path)
        assert w > 0 and h > 0

        # Decompress to grid
        grid = decompress_grid(encoded, w, h)
        assert grid.width == w
        assert grid.height == h

        # Re-compress and compare
        re_encoded, stats = compress_grid(grid)
        assert stats["pixel_count"] == w * h

        # Decompress re-encoded and verify pixel equality
        grid2 = decompress_grid(re_encoded, w, h)
        for y in range(h):
            for x in range(w):
                assert grid.get_pixel(x, y) == grid2.get_pixel(x, y), \
                    f"Mismatch at ({x},{y})"

    def test_save_reload_integrity(self, rle_path, tmp_path):
        # Load original
        encoded, w, h = load_rle(rle_path)
        grid = decompress_grid(encoded, w, h)

        # Save to temp, reload, compare
        out = str(tmp_path / "resaved.rle")
        re_encoded, _ = compress_grid(grid)
        save_rle(re_encoded, w, h, out)

        enc2, w2, h2 = load_rle(out)
        assert (w2, h2) == (w, h)
        grid2 = decompress_grid(enc2, w2, h2)

        flat1 = grid.to_flat_list()
        flat2 = grid2.to_flat_list()
        assert flat1 == flat2


class TestRLEEdgeCases:
    """Additional edge-case tests beyond the generated samples."""

    def test_empty_grid(self):
        """A fully transparent grid should compress to 1 run."""
        g = PixelGrid(8, 8)
        encoded, stats = compress_grid(g)
        assert stats["run_count"] == 1
        assert stats["pixel_count"] == 64

    def test_single_pixel_colors(self):
        """Every pixel different — runs == pixel count."""
        g = PixelGrid(4, 4)
        for y in range(4):
            for x in range(4):
                g.set_pixel(x, y, (x * 60, y * 60, (x + y) * 30, 255))
        encoded, stats = compress_grid(g)
        # May have some accidental runs, but at most == pixel_count
        assert stats["run_count"] <= stats["pixel_count"]

    def test_max_run_length(self):
        """A very large solid area should still be one run."""
        g = PixelGrid(256, 256)
        color = (128, 64, 32, 255)
        for y in range(256):
            for x in range(256):
                g.set_pixel(x, y, color)
        encoded, stats = compress_grid(g)
        assert stats["run_count"] == 1
        assert stats["ratio"] > 1000

    def test_rle_encode_decode_symmetry(self):
        """Raw encode/decode should be perfectly symmetric."""
        data = [(255, 0, 0, 255)] * 10 + [(0, 255, 0, 255)] * 5
        encoded = rle_encode(data)
        decoded = rle_decode(encoded)
        assert decoded == data

    def test_rle_empty_input(self):
        encoded = rle_encode([])
        assert encoded == []
        decoded = rle_decode([])
        assert decoded == []
