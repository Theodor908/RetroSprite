"""Tests for RoundedRectTool."""
from src.pixel_data import PixelGrid
from src.tools import RoundedRectTool


def test_rounded_rect_outline():
    grid = PixelGrid(20, 20)
    tool = RoundedRectTool()
    tool.apply(grid, 2, 2, 17, 12, (255, 0, 0, 255), radius=3, filled=False)
    assert grid.get_pixel(10, 2) == (255, 0, 0, 255)
    assert grid.get_pixel(10, 7) == (0, 0, 0, 0)


def test_rounded_rect_filled():
    grid = PixelGrid(20, 20)
    tool = RoundedRectTool()
    tool.apply(grid, 2, 2, 17, 12, (0, 255, 0, 255), radius=3, filled=True)
    assert grid.get_pixel(10, 7) == (0, 255, 0, 255)
    assert grid.get_pixel(0, 0) == (0, 0, 0, 0)


def test_rounded_rect_radius_clamped():
    grid = PixelGrid(10, 10)
    tool = RoundedRectTool()
    tool.apply(grid, 3, 3, 6, 6, (255, 0, 0, 255), radius=10, filled=False)
    assert grid.get_pixel(3, 3) == (255, 0, 0, 255)


def test_rounded_rect_radius_zero_is_regular_rect():
    grid = PixelGrid(10, 10)
    tool = RoundedRectTool()
    tool.apply(grid, 2, 2, 7, 7, (255, 0, 0, 255), radius=0, filled=False)
    assert grid.get_pixel(2, 2) == (255, 0, 0, 255)


def test_rounded_rect_small_rect():
    grid = PixelGrid(10, 10)
    tool = RoundedRectTool()
    tool.apply(grid, 4, 4, 5, 5, (255, 0, 0, 255), radius=2, filled=True)
    assert grid.get_pixel(4, 4) == (255, 0, 0, 255)
