"""Integration tests for multi-project / ProjectContext behaviour."""
from src.project_context import ProjectContext
from src.animation import AnimationTimeline
from src.palette import Palette


def test_clipboard_shared_across_contexts():
    """Clipboard is not stored in ProjectContext — it's global."""
    ctx1 = ProjectContext.create_new(width=32, height=32)
    ctx2 = ProjectContext.create_new(width=32, height=32)
    # Clipboard is on the app, not on the context
    assert not hasattr(ctx1, '_clipboard')
    assert not hasattr(ctx2, '_clipboard')


def test_context_from_loaded():
    """from_loaded creates a context with the right name and path."""
    tl = AnimationTimeline(64, 64)
    pal = Palette("Pico-8")
    ctx = ProjectContext.from_loaded(
        timeline=tl, palette=pal, path="/tmp/test.retro"
    )
    assert ctx.name == "test.retro"
    assert ctx.project_path == "/tmp/test.retro"
    assert ctx.timeline is tl
    assert ctx.palette is pal
    assert ctx.dirty is False


def test_context_symmetry_defaults_to_center():
    """Symmetry axes default to canvas center."""
    ctx = ProjectContext.create_new(width=100, height=60)
    assert ctx.symmetry_axis_x == 50
    assert ctx.symmetry_axis_y == 30
