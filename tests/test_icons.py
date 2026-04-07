# tests/test_icons.py
import pytest
from PIL import Image
from src.ui.icons import IconPipeline


def test_pipeline_pixelate():
    pipeline = IconPipeline(icon_size=16, display_size=32)
    # Create a simple test icon (white circle on black)
    src = Image.new("RGBA", (64, 64), (0, 0, 0, 255))
    result = pipeline.prepare(src, line_color=(0, 240, 255))
    assert result.size == (32, 32)
    assert result.mode == "RGBA"


def test_pipeline_pixelate_with_glow():
    pipeline = IconPipeline(icon_size=16, display_size=32)
    src = Image.new("RGBA", (64, 64), (0, 0, 0, 255))
    # Draw a white cross
    for i in range(64):
        src.putpixel((32, i), (255, 255, 255, 255))
        src.putpixel((i, 32), (255, 255, 255, 255))
    normal, glow = pipeline.create_tool_icon(src, line_color=(0, 240, 255))
    assert normal.size == (32, 32)
    assert glow.size == (32, 32)


def test_pipeline_get_icon_returns_cached():
    pipeline = IconPipeline(icon_size=16, display_size=32)
    # Without actual icon files, test that missing icon returns a fallback
    result = pipeline.get_icon("nonexistent_tool")
    assert result is not None  # Should return a fallback icon
