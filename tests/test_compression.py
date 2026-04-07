"""Tests for RLE compression."""
import pytest
from src.compression import rle_encode, rle_decode, compress_grid, decompress_grid
from src.pixel_data import PixelGrid


class TestRLEEncode:
    def test_single_run(self):
        data = [(255, 0, 0, 255)] * 5
        encoded = rle_encode(data)
        assert encoded == [(5, (255, 0, 0, 255))]

    def test_multiple_runs(self):
        data = [(255, 0, 0, 255)] * 3 + [(0, 255, 0, 255)] * 2
        encoded = rle_encode(data)
        assert encoded == [(3, (255, 0, 0, 255)), (2, (0, 255, 0, 255))]

    def test_alternating_pixels(self):
        r = (255, 0, 0, 255)
        b = (0, 0, 255, 255)
        data = [r, b, r, b]
        encoded = rle_encode(data)
        assert encoded == [(1, r), (1, b), (1, r), (1, b)]

    def test_empty_data(self):
        assert rle_encode([]) == []

    def test_single_pixel(self):
        data = [(128, 128, 128, 255)]
        encoded = rle_encode(data)
        assert encoded == [(1, (128, 128, 128, 255))]


class TestRLEDecode:
    def test_decode_single_run(self):
        encoded = [(5, (255, 0, 0, 255))]
        decoded = rle_decode(encoded)
        assert decoded == [(255, 0, 0, 255)] * 5

    def test_decode_multiple_runs(self):
        encoded = [(3, (255, 0, 0, 255)), (2, (0, 255, 0, 255))]
        decoded = rle_decode(encoded)
        assert decoded == [(255, 0, 0, 255)] * 3 + [(0, 255, 0, 255)] * 2

    def test_empty(self):
        assert rle_decode([]) == []

    def test_roundtrip(self):
        r = (255, 0, 0, 255)
        g = (0, 255, 0, 255)
        original = [r, r, r, g, g, r]
        assert rle_decode(rle_encode(original)) == original


class TestGridCompression:
    def test_compress_uniform_grid(self):
        grid = PixelGrid(8, 8)  # All transparent
        encoded, stats = compress_grid(grid)
        assert stats["original_size"] > 0
        assert stats["compressed_size"] > 0
        assert stats["ratio"] > 1.0  # Should compress well

    def test_compress_decompress_roundtrip(self):
        grid = PixelGrid(4, 4)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        grid.set_pixel(1, 1, (0, 255, 0, 255))
        encoded, stats = compress_grid(grid)
        restored = decompress_grid(encoded, 4, 4)
        assert restored.get_pixel(0, 0) == (255, 0, 0, 255)
        assert restored.get_pixel(1, 1) == (0, 255, 0, 255)
        assert restored.get_pixel(2, 2) == (0, 0, 0, 0)
