"""Tests for Contour Fill mode."""
from src.pixel_data import PixelGrid
from src.tools import FillTool


def test_contour_fill_square():
    grid = PixelGrid(10, 10)
    white = (255, 255, 255, 255)
    red = (255, 0, 0, 255)
    for x in range(2, 7):
        for y in range(2, 7):
            grid.set_pixel(x, y, white)
    tool = FillTool()
    tool.apply(grid, 4, 4, red, contour=True)
    assert grid.get_pixel(2, 2) == red
    assert grid.get_pixel(6, 2) == red
    assert grid.get_pixel(2, 6) == red
    assert grid.get_pixel(4, 4) == white


def test_contour_fill_single_pixel():
    grid = PixelGrid(10, 10)
    white = (255, 255, 255, 255)
    red = (255, 0, 0, 255)
    grid.set_pixel(5, 5, white)
    tool = FillTool()
    tool.apply(grid, 5, 5, red, contour=True)
    assert grid.get_pixel(5, 5) == red


def test_normal_fill_unchanged():
    grid = PixelGrid(10, 10)
    red = (255, 0, 0, 255)
    tool = FillTool()
    tool.apply(grid, 0, 0, red, contour=False)
    assert grid.get_pixel(5, 5) == red
    assert grid.get_pixel(9, 9) == red


def test_contour_fill_on_transparent():
    grid = PixelGrid(10, 10)
    white = (255, 255, 255, 255)
    blue = (0, 0, 255, 255)
    grid.set_pixel(5, 5, white)
    tool = FillTool()
    tool.apply(grid, 0, 0, blue, contour=True)
    assert grid.get_pixel(4, 5) == blue
    assert grid.get_pixel(6, 5) == blue
    assert grid.get_pixel(0, 0) == blue
