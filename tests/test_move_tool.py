"""Tests for move tool logic (pixel shifting)."""
import numpy as np
from src.pixel_data import PixelGrid
from src.input_handler import _shift_grid


def test_shift_right():
    grid = PixelGrid(5, 5)
    grid.set_pixel(0, 0, (255, 0, 0, 255))
    result = _shift_grid(grid, 2, 0)
    assert result.get_pixel(2, 0) == (255, 0, 0, 255)
    assert result.get_pixel(0, 0) == (0, 0, 0, 0)


def test_shift_down():
    grid = PixelGrid(5, 5)
    grid.set_pixel(0, 0, (255, 0, 0, 255))
    result = _shift_grid(grid, 0, 3)
    assert result.get_pixel(0, 3) == (255, 0, 0, 255)
    assert result.get_pixel(0, 0) == (0, 0, 0, 0)


def test_shift_clips_at_boundary():
    grid = PixelGrid(5, 5)
    grid.set_pixel(4, 4, (255, 0, 0, 255))
    result = _shift_grid(grid, 2, 0)
    assert result.get_pixel(4, 4) == (0, 0, 0, 0)


def test_shift_zero():
    grid = PixelGrid(5, 5)
    grid.set_pixel(2, 2, (255, 0, 0, 255))
    result = _shift_grid(grid, 0, 0)
    assert result.get_pixel(2, 2) == (255, 0, 0, 255)
