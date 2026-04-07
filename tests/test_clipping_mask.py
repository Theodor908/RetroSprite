"""Tests for Clipping Masks."""
import numpy as np
from src.pixel_data import PixelGrid
from src.layer import Layer, flatten_layers


def test_layer_has_clipping_field():
    layer = Layer("Test", 4, 4)
    assert hasattr(layer, 'clipping')
    assert layer.clipping is False


def test_clipping_mask_hides_outside_base():
    base = Layer("Base", 4, 4)
    base.pixels.set_pixel(0, 0, (255, 0, 0, 255))
    base.pixels.set_pixel(1, 0, (255, 0, 0, 255))
    base.pixels.set_pixel(0, 1, (255, 0, 0, 255))
    base.pixels.set_pixel(1, 1, (255, 0, 0, 255))

    clip = Layer("Clip", 4, 4)
    clip.clipping = True
    for x in range(4):
        for y in range(4):
            clip.pixels.set_pixel(x, y, (0, 0, 255, 255))

    result = flatten_layers([base, clip], 4, 4)
    p00 = result.get_pixel(0, 0)
    assert p00 == (0, 0, 255, 255)
    p22 = result.get_pixel(2, 2)
    assert p22 == (0, 0, 0, 0)


def test_clipping_bottom_layer_treated_as_normal():
    layer = Layer("Bottom", 4, 4)
    layer.clipping = True
    layer.pixels.set_pixel(0, 0, (255, 0, 0, 255))
    result = flatten_layers([layer], 4, 4)
    assert result.get_pixel(0, 0) == (255, 0, 0, 255)


def test_multiple_clipped_layers():
    base = Layer("Base", 4, 4)
    base.pixels.set_pixel(0, 0, (255, 0, 0, 255))

    clip1 = Layer("Clip1", 4, 4)
    clip1.clipping = True
    clip1.pixels.set_pixel(0, 0, (0, 255, 0, 128))

    clip2 = Layer("Clip2", 4, 4)
    clip2.clipping = True
    clip2.pixels.set_pixel(0, 0, (0, 0, 255, 128))

    result = flatten_layers([base, clip1, clip2], 4, 4)
    p = result.get_pixel(0, 0)
    assert p[3] > 0
    assert result.get_pixel(2, 2) == (0, 0, 0, 0)


def test_clipping_with_half_opacity_base():
    base = Layer("Base", 4, 4)
    base.opacity = 0.5
    base.pixels.set_pixel(0, 0, (255, 0, 0, 255))

    clip = Layer("Clip", 4, 4)
    clip.clipping = True
    clip.pixels.set_pixel(0, 0, (0, 0, 255, 255))
    clip.pixels.set_pixel(2, 2, (0, 0, 255, 255))

    result = flatten_layers([base, clip], 4, 4)
    assert result.get_pixel(0, 0)[3] > 0
    assert result.get_pixel(2, 2) == (0, 0, 0, 0)


def test_layer_copy_preserves_clipping():
    layer = Layer("Test", 4, 4)
    layer.clipping = True
    copied = layer.copy()
    assert copied.clipping is True
