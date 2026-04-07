# tests/test_timeline.py
import pytest
from src.animation import AnimationTimeline
from src.layer import Layer
from src.pixel_data import PixelGrid


def test_timeline_frame_durations():
    tl = AnimationTimeline(16, 16)
    tl.add_frame()
    tl.add_frame()
    # Default durations
    assert tl.current_frame_obj().duration_ms == 100
    # Set per-frame
    tl.set_current(1)
    tl.current_frame_obj().duration_ms = 200
    tl.set_current(2)
    tl.current_frame_obj().duration_ms = 50
    # Verify
    tl.set_current(0)
    assert tl.current_frame_obj().duration_ms == 100
    tl.set_current(1)
    assert tl.current_frame_obj().duration_ms == 200
    tl.set_current(2)
    assert tl.current_frame_obj().duration_ms == 50


def test_timeline_layer_lock():
    layer = Layer("Test", 16, 16)
    assert layer.locked == False
    layer.locked = True
    assert layer.locked == True
