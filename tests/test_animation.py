"""Tests for animation frame management."""
import os
import pytest
from src.animation import AnimationTimeline, Frame
from src.pixel_data import PixelGrid


class TestFrame:
    def test_starts_with_one_layer(self):
        frame = Frame(8, 8)
        assert len(frame.layers) == 1
        assert frame.active_layer_index == 0

    def test_add_layer(self):
        frame = Frame(8, 8)
        frame.add_layer("Layer 2")
        assert len(frame.layers) == 2
        assert frame.active_layer_index == 1

    def test_remove_layer(self):
        frame = Frame(8, 8)
        frame.add_layer("Layer 2")
        frame.remove_layer(1)
        assert len(frame.layers) == 1
        assert frame.active_layer_index == 0

    def test_cannot_remove_last_layer(self):
        frame = Frame(8, 8)
        frame.remove_layer(0)
        assert len(frame.layers) == 1

    def test_duplicate_layer(self):
        frame = Frame(8, 8)
        frame.layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))
        copy = frame.duplicate_layer(0)
        assert len(frame.layers) == 2
        assert copy.pixels.get_pixel(0, 0) == (255, 0, 0, 255)
        # Ensure it's a deep copy
        copy.pixels.set_pixel(0, 0, (0, 0, 0, 0))
        assert frame.layers[0].pixels.get_pixel(0, 0) == (255, 0, 0, 255)

    def test_merge_down(self):
        frame = Frame(8, 8)
        frame.layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))
        frame.add_layer("Top")
        frame.layers[1].pixels.set_pixel(0, 0, (0, 255, 0, 255))
        frame.merge_down(1)
        assert len(frame.layers) == 1
        assert frame.layers[0].pixels.get_pixel(0, 0) == (0, 255, 0, 255)

    def test_flatten(self):
        frame = Frame(8, 8)
        frame.layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))
        result = frame.flatten()
        assert result.get_pixel(0, 0) == (255, 0, 0, 255)

    def test_copy(self):
        frame = Frame(8, 8)
        frame.layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))
        copy = frame.copy()
        assert copy.flatten().get_pixel(0, 0) == (255, 0, 0, 255)
        copy.layers[0].pixels.set_pixel(0, 0, (0, 0, 0, 0))
        assert frame.layers[0].pixels.get_pixel(0, 0) == (255, 0, 0, 255)


class TestAnimationTimeline:
    def test_starts_with_one_frame(self):
        timeline = AnimationTimeline(16, 16)
        assert timeline.frame_count == 1

    def test_add_frame(self):
        timeline = AnimationTimeline(16, 16)
        timeline.add_frame()
        assert timeline.frame_count == 2

    def test_current_frame(self):
        timeline = AnimationTimeline(8, 8)
        frame = timeline.current_frame()
        assert isinstance(frame, PixelGrid)
        assert frame.width == 8

    def test_current_layer(self):
        timeline = AnimationTimeline(8, 8)
        layer = timeline.current_layer()
        assert isinstance(layer, PixelGrid)
        layer.set_pixel(0, 0, (255, 0, 0, 255))
        assert timeline.current_frame().get_pixel(0, 0) == (255, 0, 0, 255)

    def test_switch_frame(self):
        timeline = AnimationTimeline(8, 8)
        timeline.current_layer().set_pixel(0, 0, (255, 0, 0, 255))
        timeline.add_frame()
        timeline.set_current(1)
        assert timeline.current_frame().get_pixel(0, 0) == (0, 0, 0, 0)
        timeline.set_current(0)
        assert timeline.current_frame().get_pixel(0, 0) == (255, 0, 0, 255)

    def test_duplicate_frame(self):
        timeline = AnimationTimeline(8, 8)
        timeline.current_layer().set_pixel(0, 0, (255, 0, 0, 255))
        timeline.duplicate_frame(0)
        assert timeline.frame_count == 2
        assert timeline.get_frame(1).get_pixel(0, 0) == (255, 0, 0, 255)
        # Duplicate is independent - pixels are not shared
        f0 = timeline.get_frame_obj(0)
        f1 = timeline.get_frame_obj(1)
        assert f0.layers[0].pixels is not f1.layers[0].pixels
        assert f0.layers[0].cel_id != f1.layers[0].cel_id

    def test_duplicate_frame_unlinked_after_unlink(self):
        timeline = AnimationTimeline(8, 8)
        timeline.current_layer().set_pixel(0, 0, (255, 0, 0, 255))
        timeline.duplicate_frame(0)
        # Unlink the duplicate so edits are independent
        timeline.get_frame_obj(1).layers[0].unlink()
        timeline.get_frame_obj(1).active_layer.pixels.set_pixel(0, 0, (0, 0, 0, 0))
        assert timeline.get_frame(0).get_pixel(0, 0) == (255, 0, 0, 255)

    def test_remove_frame(self):
        timeline = AnimationTimeline(8, 8)
        timeline.add_frame()
        timeline.add_frame()
        timeline.remove_frame(1)
        assert timeline.frame_count == 2

    def test_cannot_remove_last_frame(self):
        timeline = AnimationTimeline(8, 8)
        timeline.remove_frame(0)
        assert timeline.frame_count == 1

    def test_move_frame(self):
        timeline = AnimationTimeline(8, 8)
        timeline.current_layer().set_pixel(0, 0, (255, 0, 0, 255))
        timeline.add_frame()
        timeline.set_current(1)
        timeline.current_layer().set_pixel(0, 0, (0, 255, 0, 255))
        timeline.move_frame(0, 1)
        assert timeline.get_frame(0).get_pixel(0, 0) == (0, 255, 0, 255)
        assert timeline.get_frame(1).get_pixel(0, 0) == (255, 0, 0, 255)

    def test_export_gif(self, tmp_path):
        timeline = AnimationTimeline(8, 8)
        timeline.current_layer().set_pixel(0, 0, (255, 0, 0, 255))
        timeline.add_frame()
        timeline.set_current(1)
        timeline.current_layer().set_pixel(0, 0, (0, 255, 0, 255))
        path = str(tmp_path / "test.gif")
        timeline.export_gif(path, fps=10, scale=1)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0

    def test_current_frame_obj(self):
        timeline = AnimationTimeline(8, 8)
        frame_obj = timeline.current_frame_obj()
        assert isinstance(frame_obj, Frame)
        assert len(frame_obj.layers) == 1

    def test_get_frame_obj(self):
        timeline = AnimationTimeline(8, 8)
        timeline.add_frame()
        frame_obj = timeline.get_frame_obj(1)
        assert isinstance(frame_obj, Frame)


class TestFrameDuration:
    def test_frame_default_duration(self):
        frame = Frame(16, 16)
        assert frame.duration_ms == 100

    def test_frame_custom_duration(self):
        frame = Frame(16, 16)
        frame.duration_ms = 200
        assert frame.duration_ms == 200

    def test_timeline_per_frame_durations(self):
        tl = AnimationTimeline(16, 16)
        tl.add_frame()  # frame 2
        tl.set_current(1)
        tl.current_frame_obj().duration_ms = 200
        tl.set_current(0)
        assert tl.current_frame_obj().duration_ms == 100
        tl.set_current(1)
        assert tl.current_frame_obj().duration_ms == 200

    def test_frame_copy_preserves_duration(self):
        frame = Frame(16, 16)
        frame.duration_ms = 250
        copied = frame.copy()
        assert copied.duration_ms == 250


class TestFrameTags:
    def test_add_tag(self):
        tl = AnimationTimeline(8, 8)
        tl.add_frame()
        tl.add_frame()
        tl.add_tag("idle", "#00ff00", 0, 1)
        assert len(tl.tags) == 1
        assert tl.tags[0]["name"] == "idle"

    def test_get_tags_for_frame(self):
        tl = AnimationTimeline(8, 8)
        tl.add_frame()
        tl.add_frame()
        tl.add_tag("idle", "#00ff00", 0, 1)
        tl.add_tag("walk", "#ff0000", 2, 2)
        assert len(tl.get_tags_for_frame(0)) == 1
        assert len(tl.get_tags_for_frame(2)) == 1
        assert tl.get_tags_for_frame(0)[0]["name"] == "idle"

    def test_remove_tag(self):
        tl = AnimationTimeline(8, 8)
        tl.add_tag("idle", "#00ff00", 0, 0)
        tl.remove_tag(0)
        assert len(tl.tags) == 0
