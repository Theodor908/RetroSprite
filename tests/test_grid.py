"""Tests for grid settings dataclass."""
import pytest
from src.grid import GridSettings


class TestGridSettings:
    def test_defaults(self):
        gs = GridSettings()
        assert gs.pixel_grid_visible is True
        assert gs.pixel_grid_color == (180, 180, 180, 80)
        assert gs.pixel_grid_min_zoom == 4
        assert gs.custom_grid_visible is False
        assert gs.custom_grid_width == 16
        assert gs.custom_grid_height == 16
        assert gs.custom_grid_offset_x == 0
        assert gs.custom_grid_offset_y == 0
        assert gs.custom_grid_color == (0, 240, 255, 120)

    def test_to_dict_roundtrip(self):
        gs = GridSettings(
            pixel_grid_visible=False,
            pixel_grid_color=(255, 0, 0, 200),
            pixel_grid_min_zoom=8,
            custom_grid_visible=True,
            custom_grid_width=32,
            custom_grid_height=24,
            custom_grid_offset_x=4,
            custom_grid_offset_y=8,
            custom_grid_color=(0, 255, 0, 100),
        )
        d = gs.to_dict()
        restored = GridSettings.from_dict(d)
        assert restored == gs

    def test_from_dict_missing_fields(self):
        d = {"pixel_visible": False, "custom_width": 8}
        gs = GridSettings.from_dict(d)
        assert gs.pixel_grid_visible is False
        assert gs.custom_grid_width == 8
        assert gs.pixel_grid_color == (180, 180, 180, 80)
        assert gs.custom_grid_visible is False
        assert gs.custom_grid_height == 16

    def test_from_dict_empty(self):
        gs = GridSettings.from_dict({})
        default = GridSettings()
        assert gs == default

    def test_pixel_grid_color_rgba(self):
        gs = GridSettings()
        assert len(gs.pixel_grid_color) == 4
        assert len(gs.custom_grid_color) == 4

    def test_custom_grid_dimensions_clamped(self):
        gs = GridSettings(custom_grid_width=0, custom_grid_height=-5)
        assert gs.custom_grid_width >= 1
        assert gs.custom_grid_height >= 1


class TestGridPersistence:
    def test_grid_settings_in_project_dict(self):
        """Grid settings should serialize to a dict matching the .retro format."""
        gs = GridSettings(custom_grid_visible=True, custom_grid_width=32)
        d = gs.to_dict()
        assert d["custom_visible"] is True
        assert d["custom_width"] == 32
        restored = GridSettings.from_dict(d)
        assert restored.custom_grid_visible is True
        assert restored.custom_grid_width == 32


class TestGridSnap:
    def test_snap_basic(self):
        gs = GridSettings(custom_grid_visible=True, custom_grid_width=8, custom_grid_height=8)
        assert gs.snap(5, 5) == (8, 8)

    def test_snap_exact(self):
        gs = GridSettings(custom_grid_visible=True, custom_grid_width=8, custom_grid_height=8)
        assert gs.snap(16, 16) == (16, 16)

    def test_snap_with_offset(self):
        gs = GridSettings(custom_grid_visible=True, custom_grid_width=8, custom_grid_height=8,
                          custom_grid_offset_x=4, custom_grid_offset_y=4)
        assert gs.snap(5, 5) == (4, 4)

    def test_snap_grid_not_visible(self):
        gs = GridSettings(custom_grid_visible=False, custom_grid_width=8, custom_grid_height=8)
        assert gs.snap(5, 5) == (5, 5)

    def test_snap_rounds_nearest(self):
        gs = GridSettings(custom_grid_visible=True, custom_grid_width=8, custom_grid_height=8)
        assert gs.snap(3, 3) == (0, 0)
        assert gs.snap(5, 5) == (8, 8)

    def test_snap_negative(self):
        gs = GridSettings(custom_grid_visible=True, custom_grid_width=8, custom_grid_height=8)
        assert gs.snap(0, 0) == (0, 0)
