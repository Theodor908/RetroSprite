"""Tests for pixel data model."""
import pytest
from src.pixel_data import PixelGrid


class TestPixelGrid:
    def test_create_with_dimensions(self):
        grid = PixelGrid(16, 16)
        assert grid.width == 16
        assert grid.height == 16

    def test_default_color_is_transparent(self):
        grid = PixelGrid(8, 8)
        assert grid.get_pixel(0, 0) == (0, 0, 0, 0)

    def test_set_and_get_pixel(self):
        grid = PixelGrid(8, 8)
        grid.set_pixel(3, 4, (255, 0, 0, 255))
        assert grid.get_pixel(3, 4) == (255, 0, 0, 255)

    def test_out_of_bounds_returns_none(self):
        grid = PixelGrid(8, 8)
        assert grid.get_pixel(8, 8) is None
        assert grid.get_pixel(-1, 0) is None

    def test_clear(self):
        grid = PixelGrid(8, 8)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        grid.clear()
        assert grid.get_pixel(0, 0) == (0, 0, 0, 0)

    def test_to_flat_list(self):
        grid = PixelGrid(2, 2)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        grid.set_pixel(1, 0, (0, 255, 0, 255))
        flat = grid.to_flat_list()
        assert flat[0] == (255, 0, 0, 255)
        assert flat[1] == (0, 255, 0, 255)

    def test_from_pil_image(self):
        from PIL import Image
        img = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
        grid = PixelGrid.from_pil_image(img)
        assert grid.width == 4
        assert grid.height == 4
        assert grid.get_pixel(0, 0) == (255, 0, 0, 255)

    def test_to_pil_image(self):
        grid = PixelGrid(4, 4)
        grid.set_pixel(0, 0, (0, 128, 255, 255))
        img = grid.to_pil_image()
        assert img.size == (4, 4)
        assert img.getpixel((0, 0)) == (0, 128, 255, 255)

    def test_copy(self):
        grid = PixelGrid(4, 4)
        grid.set_pixel(1, 1, (255, 0, 0, 255))
        copy = grid.copy()
        copy.set_pixel(1, 1, (0, 255, 0, 255))
        assert grid.get_pixel(1, 1) == (255, 0, 0, 255)
        assert copy.get_pixel(1, 1) == (0, 255, 0, 255)

    def test_extract_region(self):
        grid = PixelGrid(8, 8)
        grid.set_pixel(2, 2, (255, 0, 0, 255))
        grid.set_pixel(3, 3, (0, 255, 0, 255))
        region = grid.extract_region(2, 2, 3, 3)
        assert region.width == 3
        assert region.height == 3
        assert region.get_pixel(0, 0) == (255, 0, 0, 255)
        assert region.get_pixel(1, 1) == (0, 255, 0, 255)
        assert region.get_pixel(2, 2) == (0, 0, 0, 0)

    def test_extract_region_clamps_to_bounds(self):
        grid = PixelGrid(4, 4)
        grid.set_pixel(3, 3, (255, 0, 0, 255))
        region = grid.extract_region(3, 3, 4, 4)
        assert region.width == 4
        assert region.height == 4
        assert region.get_pixel(0, 0) == (255, 0, 0, 255)
        # Out-of-bounds pixels remain transparent
        assert region.get_pixel(1, 1) == (0, 0, 0, 0)

    def test_paste_region(self):
        grid = PixelGrid(8, 8)
        source = PixelGrid(2, 2)
        source.set_pixel(0, 0, (255, 0, 0, 255))
        source.set_pixel(1, 1, (0, 255, 0, 255))
        grid.paste_region(source, 3, 3)
        assert grid.get_pixel(3, 3) == (255, 0, 0, 255)
        assert grid.get_pixel(4, 4) == (0, 255, 0, 255)
        # Transparent source pixels don't overwrite
        assert grid.get_pixel(4, 3) == (0, 0, 0, 0)

    def test_paste_region_skips_transparent(self):
        grid = PixelGrid(4, 4)
        grid.set_pixel(0, 0, (100, 100, 100, 255))
        source = PixelGrid(2, 2)
        # source pixel (0,0) is transparent — should not overwrite
        source.set_pixel(1, 0, (255, 0, 0, 255))
        grid.paste_region(source, 0, 0)
        assert grid.get_pixel(0, 0) == (100, 100, 100, 255)
        assert grid.get_pixel(1, 0) == (255, 0, 0, 255)

    def test_extract_then_paste_roundtrip(self):
        grid = PixelGrid(8, 8)
        grid.set_pixel(1, 1, (255, 0, 0, 255))
        grid.set_pixel(2, 1, (0, 255, 0, 255))
        region = grid.extract_region(1, 1, 2, 1)
        target = PixelGrid(8, 8)
        target.paste_region(region, 5, 5)
        assert target.get_pixel(5, 5) == (255, 0, 0, 255)
        assert target.get_pixel(6, 5) == (0, 255, 0, 255)
