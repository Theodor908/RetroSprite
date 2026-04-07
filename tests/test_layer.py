"""Tests for layer model."""
import pytest
import numpy as np
from src.layer import Layer, flatten_layers, apply_blend_mode
from src.pixel_data import PixelGrid


RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


class TestLayer:
    def test_create_layer(self):
        layer = Layer("Background", 8, 8)
        assert layer.name == "Background"
        assert layer.visible is True
        assert layer.opacity == 1.0
        assert layer.blend_mode == "normal"
        assert layer.locked is False
        assert layer.pixels.width == 8

    def test_layer_from_grid(self):
        grid = PixelGrid(4, 4)
        grid.set_pixel(0, 0, RED)
        layer = Layer.from_grid("Test", grid)
        assert layer.pixels.get_pixel(0, 0) == RED

    def test_layer_copy(self):
        layer = Layer("Original", 4, 4)
        layer.pixels.set_pixel(0, 0, RED)
        copy = layer.copy()
        copy.pixels.set_pixel(0, 0, GREEN)
        assert layer.pixels.get_pixel(0, 0) == RED
        assert copy.name == "Original Copy"


class TestFlattenLayers:
    def test_single_layer(self):
        layer = Layer("Base", 4, 4)
        layer.pixels.set_pixel(0, 0, RED)
        result = flatten_layers([layer], 4, 4)
        assert result.get_pixel(0, 0) == RED

    def test_two_layers_opaque(self):
        bottom = Layer("Bottom", 4, 4)
        bottom.pixels.set_pixel(0, 0, RED)
        top = Layer("Top", 4, 4)
        top.pixels.set_pixel(0, 0, GREEN)
        result = flatten_layers([bottom, top], 4, 4)
        assert result.get_pixel(0, 0) == GREEN

    def test_hidden_layer_ignored(self):
        bottom = Layer("Bottom", 4, 4)
        bottom.pixels.set_pixel(0, 0, RED)
        top = Layer("Top", 4, 4)
        top.pixels.set_pixel(0, 0, GREEN)
        top.visible = False
        result = flatten_layers([bottom, top], 4, 4)
        assert result.get_pixel(0, 0) == RED

    def test_layer_opacity(self):
        bottom = Layer("Bottom", 4, 4)
        bottom.pixels.set_pixel(0, 0, RED)
        top = Layer("Top", 4, 4)
        top.pixels.set_pixel(0, 0, GREEN)
        top.opacity = 0.5
        result = flatten_layers([bottom, top], 4, 4)
        pixel = result.get_pixel(0, 0)
        assert pixel[0] < 200  # Red reduced
        assert pixel[1] > 50   # Green present
        assert pixel[3] == 255  # Fully opaque

    def test_empty_layers(self):
        result = flatten_layers([], 4, 4)
        assert result.get_pixel(0, 0) == TRANSPARENT


class TestBlendModes:
    def _make_arrays(self, base_rgb, blend_rgb):
        base = np.array([[list(base_rgb) + [255]]], dtype=np.uint8)
        blend = np.array([[list(blend_rgb) + [255]]], dtype=np.uint8)
        return base, blend

    def test_normal_mode(self):
        base, blend = self._make_arrays((100, 100, 100), (200, 200, 200))
        result = apply_blend_mode(base, blend, "normal")
        assert tuple(result[0, 0, :3]) == (200, 200, 200)

    def test_multiply(self):
        base, blend = self._make_arrays((200, 100, 50), (128, 255, 0))
        result = apply_blend_mode(base, blend, "multiply")
        assert tuple(result[0, 0, :3]) == (200*128//255, 100*255//255, 0)

    def test_screen(self):
        base, blend = self._make_arrays((100, 100, 100), (100, 100, 100))
        result = apply_blend_mode(base, blend, "screen")
        expected = 255 - (155 * 155) // 255
        assert tuple(result[0, 0, :3]) == (expected, expected, expected)

    def test_addition(self):
        base, blend = self._make_arrays((200, 100, 50), (100, 200, 250))
        result = apply_blend_mode(base, blend, "addition")
        assert tuple(result[0, 0, :3]) == (255, 255, 255)

    def test_subtract(self):
        base, blend = self._make_arrays((200, 100, 50), (50, 150, 100))
        result = apply_blend_mode(base, blend, "subtract")
        assert tuple(result[0, 0, :3]) == (150, 0, 0)

    def test_darken(self):
        base, blend = self._make_arrays((200, 50, 100), (100, 100, 100))
        result = apply_blend_mode(base, blend, "darken")
        assert tuple(result[0, 0, :3]) == (100, 50, 100)

    def test_lighten(self):
        base, blend = self._make_arrays((200, 50, 100), (100, 100, 100))
        result = apply_blend_mode(base, blend, "lighten")
        assert tuple(result[0, 0, :3]) == (200, 100, 100)

    def test_difference(self):
        base, blend = self._make_arrays((200, 50, 100), (100, 100, 100))
        result = apply_blend_mode(base, blend, "difference")
        assert tuple(result[0, 0, :3]) == (100, 50, 0)

    def test_overlay_dark(self):
        base, blend = self._make_arrays((50, 50, 50), (100, 100, 100))
        result = apply_blend_mode(base, blend, "overlay")
        expected = 2 * 50 * 100 // 255
        assert tuple(result[0, 0, :3]) == (expected, expected, expected)

    def test_overlay_light(self):
        base, blend = self._make_arrays((200, 200, 200), (100, 100, 100))
        result = apply_blend_mode(base, blend, "overlay")
        expected = 255 - 2 * 55 * 155 // 255
        assert tuple(result[0, 0, :3]) == (expected, expected, expected)

    def test_unknown_mode_falls_back_to_normal(self):
        base, blend = self._make_arrays((100, 100, 100), (200, 200, 200))
        result = apply_blend_mode(base, blend, "nonexistent")
        assert tuple(result[0, 0, :3]) == (200, 200, 200)


class TestBlendModeFlatten:
    def test_multiply_layer_compositing(self):
        bottom = Layer("bottom", 2, 2)
        bottom.pixels.set_pixel(0, 0, (200, 200, 200, 255))
        bottom.pixels.set_pixel(1, 0, (100, 100, 100, 255))

        top = Layer("top", 2, 2)
        top.blend_mode = "multiply"
        top.pixels.set_pixel(0, 0, (128, 128, 128, 255))
        top.pixels.set_pixel(1, 0, (255, 255, 255, 255))

        result = flatten_layers([bottom, top], 2, 2)
        assert result.get_pixel(0, 0)[0] == 200 * 128 // 255
        assert result.get_pixel(1, 0)[0] == 100

    def test_normal_mode_unchanged(self):
        bottom = Layer("bottom", 1, 1)
        bottom.pixels.set_pixel(0, 0, (100, 0, 0, 255))

        top = Layer("top", 1, 1)
        top.pixels.set_pixel(0, 0, (0, 200, 0, 128))

        result = flatten_layers([bottom, top], 1, 1)
        r, g, b, a = result.get_pixel(0, 0)
        assert a == 255
        assert g > 0


class TestLayerGroups:
    def test_group_compositing(self):
        """Children of a group should composite together first, then blend onto base."""
        bg = Layer("bg", 2, 1)
        bg.pixels.set_pixel(0, 0, (200, 200, 200, 255))
        bg.pixels.set_pixel(1, 0, (200, 200, 200, 255))

        group = Layer("group", 2, 1)
        group.is_group = True
        group.blend_mode = "multiply"
        group.depth = 0

        child1 = Layer("child1", 2, 1)
        child1.depth = 1
        child1.pixels.set_pixel(0, 0, (128, 128, 128, 255))

        child2 = Layer("child2", 2, 1)
        child2.depth = 1
        child2.pixels.set_pixel(1, 0, (128, 128, 128, 255))

        result = flatten_layers([bg, group, child1, child2], 2, 1)
        r0 = result.get_pixel(0, 0)[0]
        r1 = result.get_pixel(1, 0)[0]
        assert r0 == 200 * 128 // 255
        assert r1 == 200 * 128 // 255

    def test_group_opacity(self):
        """Group opacity should affect entire group result."""
        bg = Layer("bg", 1, 1)
        bg.pixels.set_pixel(0, 0, (0, 0, 0, 255))

        group = Layer("group", 1, 1)
        group.is_group = True
        group.opacity = 0.5
        group.depth = 0

        child = Layer("child", 1, 1)
        child.depth = 1
        child.pixels.set_pixel(0, 0, (200, 200, 200, 255))

        result = flatten_layers([bg, group, child], 1, 1)
        r = result.get_pixel(0, 0)[0]
        assert 95 <= r <= 105  # approximately 100

    def test_hidden_group_hides_children(self):
        """Invisible group should hide all children."""
        bg = Layer("bg", 1, 1)
        bg.pixels.set_pixel(0, 0, (100, 100, 100, 255))

        group = Layer("group", 1, 1)
        group.is_group = True
        group.visible = False
        group.depth = 0

        child = Layer("child", 1, 1)
        child.depth = 1
        child.pixels.set_pixel(0, 0, (255, 0, 0, 255))

        result = flatten_layers([bg, group, child], 1, 1)
        assert result.get_pixel(0, 0) == (100, 100, 100, 255)

    def test_flat_layers_still_work(self):
        """Layers without groups (depth=0) should composite normally."""
        l1 = Layer("l1", 1, 1)
        l1.pixels.set_pixel(0, 0, (100, 0, 0, 255))
        l2 = Layer("l2", 1, 1)
        l2.pixels.set_pixel(0, 0, (0, 200, 0, 255))
        result = flatten_layers([l1, l2], 1, 1)
        assert result.get_pixel(0, 0) == (0, 200, 0, 255)
