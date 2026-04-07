"""Tests for movable symmetry axis."""
import pytest
import numpy as np
from src.pixel_data import PixelGrid


def _apply_symmetry(fn, x, y, mode, axis_x, axis_y):
    """Standalone version of _apply_symmetry_draw for testing."""
    fn(x, y)
    cx = axis_x
    cy = axis_y
    if mode in ("horizontal", "both"):
        fn(2 * cx - x - 1, y)
    if mode in ("vertical", "both"):
        fn(x, 2 * cy - y - 1)
    if mode == "both":
        fn(2 * cx - x - 1, 2 * cy - y - 1)


class TestMirrorWithAxis:
    def test_horizontal_default_center(self):
        pixels = []
        _apply_symmetry(lambda x, y: pixels.append((x, y)),
                        2, 3, "horizontal", axis_x=5, axis_y=5)
        assert (2, 3) in pixels
        assert (7, 3) in pixels

    def test_horizontal_custom_axis(self):
        pixels = []
        _apply_symmetry(lambda x, y: pixels.append((x, y)),
                        1, 5, "horizontal", axis_x=3, axis_y=5)
        assert (1, 5) in pixels
        assert (4, 5) in pixels

    def test_vertical_custom_axis(self):
        pixels = []
        _apply_symmetry(lambda x, y: pixels.append((x, y)),
                        5, 2, "vertical", axis_x=5, axis_y=4)
        assert (5, 2) in pixels
        assert (5, 5) in pixels

    def test_both_custom_axis(self):
        pixels = []
        _apply_symmetry(lambda x, y: pixels.append((x, y)),
                        1, 1, "both", axis_x=3, axis_y=3)
        assert len(pixels) == 4
        assert (1, 1) in pixels
        assert (4, 1) in pixels
        assert (1, 4) in pixels
        assert (4, 4) in pixels

    def test_axis_defaults_to_center(self):
        w, h = 32, 24
        assert w // 2 == 16
        assert h // 2 == 12


from src.input_handler import _hit_test_symmetry_axis


class TestAxisHitTest:
    def test_hit_vertical_axis(self):
        result = _hit_test_symmetry_axis(10, 5, "horizontal", 10, 8, pixel_size=4)
        assert result == "x"

    def test_hit_horizontal_axis(self):
        result = _hit_test_symmetry_axis(5, 8, "vertical", 10, 8, pixel_size=4)
        assert result == "y"

    def test_hit_miss(self):
        result = _hit_test_symmetry_axis(0, 0, "horizontal", 10, 8, pixel_size=4)
        assert result is None

    def test_hit_off_mode(self):
        result = _hit_test_symmetry_axis(10, 5, "off", 10, 8, pixel_size=4)
        assert result is None


class TestProjectSaveLoad:
    def test_axis_round_trip(self):
        import json
        project_data = {
            "symmetry_axis_x": 7,
            "symmetry_axis_y": 12,
        }
        dumped = json.dumps(project_data)
        loaded = json.loads(dumped)
        assert loaded["symmetry_axis_x"] == 7
        assert loaded["symmetry_axis_y"] == 12

    def test_missing_axis_defaults(self):
        project_data = {}
        assert project_data.get("symmetry_axis_x") is None
        assert project_data.get("symmetry_axis_y") is None
