"""Tests for export utilities."""
import pytest
from src.export import build_sprite_sheet
from src.animation import AnimationTimeline


class TestSpriteSheet:
    def test_single_frame_sheet(self):
        tl = AnimationTimeline(8, 8)
        sheet, meta = build_sprite_sheet(tl, scale=1)
        assert sheet.size == (8, 8)
        assert len(meta["frames"]) == 1

    def test_multi_frame_horizontal(self):
        tl = AnimationTimeline(8, 8)
        tl.add_frame()
        sheet, meta = build_sprite_sheet(tl, scale=1, columns=2)
        assert sheet.size == (16, 8)
        assert len(meta["frames"]) == 2

    def test_scaled_sheet(self):
        tl = AnimationTimeline(8, 8)
        sheet, meta = build_sprite_sheet(tl, scale=2)
        assert sheet.size == (16, 16)
        assert meta["scale"] == 2

    def test_grid_layout(self):
        tl = AnimationTimeline(8, 8)
        tl.add_frame()
        tl.add_frame()
        tl.add_frame()
        sheet, meta = build_sprite_sheet(tl, scale=1, columns=2)
        # 4 frames in 2 columns = 2 rows
        assert sheet.size == (16, 16)
        assert meta["frames"][2]["x"] == 0
        assert meta["frames"][2]["y"] == 8

    def test_tags_in_metadata(self):
        tl = AnimationTimeline(8, 8)
        tl.add_frame()
        tl.add_tag("idle", "#00ff00", 0, 1)
        sheet, meta = build_sprite_sheet(tl)
        assert len(meta["tags"]) == 1
        assert meta["tags"][0]["name"] == "idle"

    def test_sprite_sheet_preserves_frame_duration(self):
        tl = AnimationTimeline(8, 8)
        tl.add_frame()
        tl.get_frame_obj(0).duration_ms = 50
        tl.get_frame_obj(1).duration_ms = 200
        sheet, meta = build_sprite_sheet(tl, scale=1)
        assert meta["frames"][0]["duration"] == 50
        assert meta["frames"][1]["duration"] == 200
