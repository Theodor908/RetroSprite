"""Tests for image processing operations."""
import pytest
from PIL import Image
from src.image_processing import (
    blur, scale, rotate, crop, flip_horizontal, flip_vertical,
    adjust_brightness, adjust_contrast, posterize
)
from src.pixel_data import PixelGrid


@pytest.fixture
def sample_grid():
    grid = PixelGrid(8, 8)
    for x in range(4):
        for y in range(8):
            grid.set_pixel(x, y, (255, 0, 0, 255))
    for x in range(4, 8):
        for y in range(8):
            grid.set_pixel(x, y, (0, 0, 255, 255))
    return grid


class TestBlur:
    def test_blur_returns_same_dimensions(self, sample_grid):
        result = blur(sample_grid, radius=1)
        assert result.width == 8
        assert result.height == 8

    def test_blur_changes_pixels(self, sample_grid):
        result = blur(sample_grid, radius=2)
        assert result.get_pixel(4, 4) != sample_grid.get_pixel(4, 4)


class TestScale:
    def test_scale_up_2x(self, sample_grid):
        result = scale(sample_grid, 2.0)
        assert result.width == 16
        assert result.height == 16

    def test_scale_down_half(self, sample_grid):
        result = scale(sample_grid, 0.5)
        assert result.width == 4
        assert result.height == 4

    def test_scale_preserves_nearest_neighbor(self):
        grid = PixelGrid(2, 2)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        grid.set_pixel(1, 0, (0, 255, 0, 255))
        grid.set_pixel(0, 1, (0, 0, 255, 255))
        grid.set_pixel(1, 1, (255, 255, 0, 255))
        result = scale(grid, 2.0)
        assert result.get_pixel(0, 0) == (255, 0, 0, 255)
        assert result.get_pixel(1, 0) == (255, 0, 0, 255)
        assert result.get_pixel(0, 1) == (255, 0, 0, 255)


class TestRotate:
    def test_rotate_90(self, sample_grid):
        result = rotate(sample_grid, 90)
        assert result.width == 8
        assert result.height == 8

    def test_rotate_180(self):
        grid = PixelGrid(2, 2)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        result = rotate(grid, 180)
        assert result.get_pixel(1, 1) == (255, 0, 0, 255)


class TestCrop:
    def test_crop_region(self, sample_grid):
        result = crop(sample_grid, x=0, y=0, w=4, h=4)
        assert result.width == 4
        assert result.height == 4
        assert result.get_pixel(0, 0) == (255, 0, 0, 255)


class TestFlip:
    def test_flip_horizontal(self):
        grid = PixelGrid(4, 1)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        result = flip_horizontal(grid)
        assert result.get_pixel(3, 0) == (255, 0, 0, 255)

    def test_flip_vertical(self):
        grid = PixelGrid(1, 4)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        result = flip_vertical(grid)
        assert result.get_pixel(0, 3) == (255, 0, 0, 255)


class TestPosterize:
    def test_posterize_reduces_colors(self):
        grid = PixelGrid(1, 1)
        grid.set_pixel(0, 0, (123, 200, 45, 255))
        result = posterize(grid, levels=2)
        pixel = result.get_pixel(0, 0)
        assert all(c in (0, 255) for c in pixel[:3])
