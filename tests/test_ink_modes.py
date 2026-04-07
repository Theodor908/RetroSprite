"""Tests for ink modes (Normal, Alpha Lock, Behind)."""
import pytest
from src.pixel_data import PixelGrid
from src.tools import PenTool, EraserTool


class TestAlphaLock:
    def test_alpha_lock_blocks_transparent_pixels(self):
        grid = PixelGrid(8, 8)
        current = grid.get_pixel(2, 2)
        assert current[3] == 0

    def test_alpha_lock_allows_opaque_pixels(self):
        grid = PixelGrid(8, 8)
        grid.set_pixel(3, 3, (100, 100, 100, 255))
        current = grid.get_pixel(3, 3)
        assert current[3] > 0

    def test_alpha_lock_preserves_transparent_area(self):
        grid = PixelGrid(8, 8)
        grid.set_pixel(4, 4, (50, 50, 50, 200))
        pen = PenTool()
        for px in range(8):
            for py in range(8):
                current = grid.get_pixel(px, py)
                if current[3] > 0:
                    pen.apply(grid, px, py, (255, 0, 0, 255))
        assert grid.get_pixel(4, 4) == (255, 0, 0, 255)
        assert grid.get_pixel(0, 0) == (0, 0, 0, 0)


class TestBehindMode:
    def test_behind_blocks_opaque_pixels(self):
        grid = PixelGrid(8, 8)
        grid.set_pixel(2, 2, (100, 200, 50, 255))
        current = grid.get_pixel(2, 2)
        assert current[3] != 0

    def test_behind_allows_transparent_pixels(self):
        grid = PixelGrid(8, 8)
        current = grid.get_pixel(5, 5)
        assert current[3] == 0

    def test_behind_preserves_existing_content(self):
        grid = PixelGrid(8, 8)
        grid.set_pixel(3, 3, (0, 255, 0, 255))
        pen = PenTool()
        for px in range(8):
            for py in range(8):
                current = grid.get_pixel(px, py)
                if current[3] == 0:
                    pen.apply(grid, px, py, (255, 0, 0, 255))
        assert grid.get_pixel(3, 3) == (0, 255, 0, 255)
        assert grid.get_pixel(0, 0) == (255, 0, 0, 255)
