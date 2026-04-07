"""Tests for PolygonTool."""
import numpy as np
from src.pixel_data import PixelGrid
from src.tools import PolygonTool


def test_polygon_outline_triangle():
    grid = PixelGrid(10, 10)
    tool = PolygonTool()
    points = [(1, 1), (8, 1), (4, 8)]
    tool.apply(grid, points, (255, 0, 0, 255), filled=False)
    assert grid.get_pixel(1, 1) == (255, 0, 0, 255)
    assert grid.get_pixel(8, 1) == (255, 0, 0, 255)
    assert grid.get_pixel(4, 8) == (255, 0, 0, 255)
    assert grid.get_pixel(4, 4) == (0, 0, 0, 0)


def test_polygon_filled_triangle():
    grid = PixelGrid(10, 10)
    tool = PolygonTool()
    points = [(1, 1), (8, 1), (4, 8)]
    tool.apply(grid, points, (0, 255, 0, 255), filled=True)
    assert grid.get_pixel(4, 3) == (0, 255, 0, 255)
    assert grid.get_pixel(0, 9) == (0, 0, 0, 0)


def test_polygon_outline_square():
    grid = PixelGrid(10, 10)
    tool = PolygonTool()
    points = [(2, 2), (7, 2), (7, 7), (2, 7)]
    tool.apply(grid, points, (255, 255, 0, 255), filled=False)
    assert grid.get_pixel(4, 2) == (255, 255, 0, 255)
    assert grid.get_pixel(4, 4) == (0, 0, 0, 0)


def test_polygon_two_points_draws_line():
    grid = PixelGrid(10, 10)
    tool = PolygonTool()
    points = [(1, 1), (5, 1)]
    tool.apply(grid, points, (255, 0, 0, 255), filled=False)
    assert grid.get_pixel(3, 1) == (255, 0, 0, 255)


def test_polygon_single_point_draws_pixel():
    grid = PixelGrid(10, 10)
    tool = PolygonTool()
    points = [(3, 3)]
    tool.apply(grid, points, (255, 0, 0, 255), filled=False)
    assert grid.get_pixel(3, 3) == (255, 0, 0, 255)


def test_polygon_with_width():
    grid = PixelGrid(20, 20)
    tool = PolygonTool()
    points = [(5, 5), (15, 5), (10, 15)]
    tool.apply(grid, points, (255, 0, 0, 255), filled=False, width=3)
    assert grid.get_pixel(10, 5) == (255, 0, 0, 255)
    assert grid.get_pixel(10, 4) == (255, 0, 0, 255)
