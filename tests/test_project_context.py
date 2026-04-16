"""Tests for ProjectContext — per-document state container."""
import pytest
from src.animation import AnimationTimeline
from src.palette import Palette
from src.project_context import ProjectContext


def test_create_default_context():
    """A new ProjectContext has sensible defaults."""
    ProjectContext._untitled_counter = 0
    ctx = ProjectContext.create_new(width=64, height=64)
    assert ctx.name == "Untitled"
    assert ctx.project_path is None
    assert ctx.dirty is False
    assert isinstance(ctx.timeline, AnimationTimeline)
    assert ctx.timeline.width == 64
    assert ctx.timeline.height == 64
    assert isinstance(ctx.palette, Palette)
    assert ctx.undo_stack == []
    assert ctx.redo_stack == []
    assert ctx.zoom_level == 1
    assert ctx.scroll_x == 0.0
    assert ctx.scroll_y == 0.0
    assert ctx.symmetry_mode == "off"
    assert ctx.playing is False
    assert ctx.onion_skin is False


def test_create_context_with_name():
    """Name can be overridden at creation."""
    ctx = ProjectContext.create_new(width=32, height=32, name="sprite.retro")
    assert ctx.name == "sprite.retro"


def test_create_context_custom_size():
    """Timeline dimensions match requested size."""
    ctx = ProjectContext.create_new(width=128, height=96)
    assert ctx.timeline.width == 128
    assert ctx.timeline.height == 96
    assert ctx.symmetry_axis_x == 64
    assert ctx.symmetry_axis_y == 48


def test_untitled_counter():
    """Multiple untitled contexts get incrementing names."""
    ProjectContext._untitled_counter = 0
    ctx1 = ProjectContext.create_new(width=32, height=32)
    ctx2 = ProjectContext.create_new(width=32, height=32)
    ctx3 = ProjectContext.create_new(width=32, height=32)
    assert ctx1.name == "Untitled"
    assert ctx2.name == "Untitled 2"
    assert ctx3.name == "Untitled 3"
