"""Tests for bitmap font rendering."""
import os
import pytest
import numpy as np
from PIL import Image

from src.bitmap_fonts import FONT_TINY, FONT_STANDARD, render_text, get_cursor_x, render_text_ttf


class TestFontData:
    def test_tiny_font_has_printable_ascii(self):
        for code in range(32, 127):
            ch = chr(code)
            assert ch in FONT_TINY["glyphs"], f"Missing glyph for {ch!r} (code {code})"

    def test_tiny_font_dimensions(self):
        assert FONT_TINY["char_width"] == 3
        assert FONT_TINY["char_height"] == 5

    def test_tiny_glyph_row_count(self):
        for ch, rows in FONT_TINY["glyphs"].items():
            assert len(rows) == 5, f"Glyph {ch!r} has {len(rows)} rows, expected 5"

    def test_tiny_glyph_row_width(self):
        max_val = (1 << FONT_TINY["char_width"]) - 1
        for ch, rows in FONT_TINY["glyphs"].items():
            for i, row in enumerate(rows):
                assert 0 <= row <= max_val, f"Glyph {ch!r} row {i} value {row} exceeds {max_val}"


class TestStandardFont:
    def test_standard_font_has_printable_ascii(self):
        for code in range(32, 127):
            ch = chr(code)
            assert ch in FONT_STANDARD["glyphs"], f"Missing glyph for {ch!r}"

    def test_standard_font_dimensions(self):
        assert FONT_STANDARD["char_width"] == 5
        assert FONT_STANDARD["char_height"] == 7

    def test_standard_glyph_row_count(self):
        for ch, rows in FONT_STANDARD["glyphs"].items():
            assert len(rows) == 7, f"Glyph {ch!r} has {len(rows)} rows, expected 7"

    def test_standard_glyph_row_width(self):
        max_val = (1 << FONT_STANDARD["char_width"]) - 1
        for ch, rows in FONT_STANDARD["glyphs"].items():
            for i, row in enumerate(rows):
                assert 0 <= row <= max_val, f"Glyph {ch!r} row {i} value {row} exceeds {max_val}"


class TestRenderText:
    def test_render_single_char(self):
        img = render_text("A", FONT_TINY, color=(255, 0, 0, 255))
        assert img.size == (3, 5)
        assert img.mode == "RGBA"

    def test_render_string_width(self):
        # "Hello" = 5 chars, each 3px wide, 1px spacing = 5*3 + 4*1 = 19
        img = render_text("Hello", FONT_TINY, color=(255, 255, 255, 255), spacing=1)
        assert img.size[0] == 19
        assert img.size[1] == 5

    def test_render_multiline_height(self):
        # "Hi\nLo" = 2 lines, each 5px tall, 2px line_height = 5 + 2 + 5 = 12
        img = render_text("Hi\nLo", FONT_TINY, color=(255, 255, 255, 255),
                          spacing=1, line_height=2)
        assert img.size[1] == 12

    def test_render_empty_string(self):
        img = render_text("", FONT_TINY, color=(255, 255, 255, 255))
        assert img.size == (1, 1)

    def test_unknown_char_fallback(self):
        img = render_text("\x80", FONT_TINY, color=(255, 0, 0, 255))
        arr = np.array(img)
        assert arr[:, :, 3].sum() > 0

    def test_spacing_affects_width(self):
        img0 = render_text("AB", FONT_TINY, color=(255, 255, 255, 255), spacing=0)
        img2 = render_text("AB", FONT_TINY, color=(255, 255, 255, 255), spacing=2)
        assert img2.size[0] > img0.size[0]

    def test_color_applied(self):
        img = render_text("A", FONT_TINY, color=(0, 255, 0, 255))
        arr = np.array(img)
        opaque = arr[arr[:, :, 3] > 0]
        assert len(opaque) > 0
        assert all(opaque[:, 1] == 255)
        assert all(opaque[:, 0] == 0)

    def test_alignment_center(self):
        img = render_text("A\nABC", FONT_TINY, color=(255, 255, 255, 255),
                          spacing=1, align="center")
        assert img.size[0] == 11  # widest line: 3*3 + 2*1 = 11

    def test_alignment_right(self):
        img = render_text("A\nABC", FONT_TINY, color=(255, 255, 255, 255),
                          spacing=1, align="right")
        assert img.size[0] == 11


class TestCursorX:
    def test_cursor_at_start(self):
        assert get_cursor_x("Hello", 0, FONT_TINY, spacing=1) == 0

    def test_cursor_at_end(self):
        assert get_cursor_x("Hello", 5, FONT_TINY, spacing=1) == 19

    def test_cursor_at_middle(self):
        # After 2 chars: 2 * (3 + 1) = 8
        assert get_cursor_x("Hello", 2, FONT_TINY, spacing=1) == 8


class TestRenderTTF:
    def _find_system_font(self):
        candidates = [
            "C:/Windows/Fonts/consola.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Menlo.ttc",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        pytest.skip("No system TTF font found for testing")

    def test_render_ttf_basic(self):
        font_path = self._find_system_font()
        img = render_text_ttf("Hello", font_path, size=16, color=(255, 0, 0, 255))
        assert img.mode == "RGBA"
        assert img.size[0] > 0 and img.size[1] > 0

    def test_render_ttf_has_opaque_pixels(self):
        font_path = self._find_system_font()
        img = render_text_ttf("A", font_path, size=24, color=(255, 255, 255, 255))
        arr = np.array(img)
        assert arr[:, :, 3].max() > 0

    def test_render_ttf_empty(self):
        font_path = self._find_system_font()
        img = render_text_ttf("", font_path, size=16, color=(255, 255, 255, 255))
        assert img.size == (1, 1)


from src.tools import TextTool
from src.pixel_data import PixelGrid


class TestTextTool:
    def test_apply_stamps_pixels(self):
        img = render_text("A", FONT_TINY, color=(255, 0, 0, 255))
        grid = PixelGrid(10, 10)
        tool = TextTool()
        tool.apply(grid, img, 2, 3)
        found = False
        for y in range(3, 8):
            for x in range(2, 5):
                px = grid.get_pixel(x, y)
                if px and px[3] > 0:
                    found = True
                    assert px[0] == 255
        assert found

    def test_apply_clips_to_canvas(self):
        img = render_text("Hello", FONT_TINY, color=(255, 255, 255, 255))
        grid = PixelGrid(5, 5)
        tool = TextTool()
        tool.apply(grid, img, -2, -1)  # Should not raise


class TestIntegration:
    def test_render_and_apply_full_flow(self):
        img = render_text("Hi", FONT_STANDARD, color=(0, 0, 255, 255), spacing=1)
        grid = PixelGrid(20, 10)
        tool = TextTool()
        tool.apply(grid, img, 1, 1)

        found_blue = False
        for y in range(1, 8):
            for x in range(1, 15):
                px = grid.get_pixel(x, y)
                if px and px[2] == 255 and px[3] == 255:
                    found_blue = True
        assert found_blue

    def test_multiline_render_standard(self):
        img = render_text("AB\nCD", FONT_STANDARD, color=(255, 255, 255, 255),
                          spacing=1, line_height=2)
        assert img.size[1] == 16  # 2*7 + 2
        assert img.size[0] == 11  # 2*5 + 1

    def test_cursor_x_with_standard_font(self):
        x = get_cursor_x("AB", 1, FONT_STANDARD, spacing=1)
        assert x == 6  # 1 * (5 + 1)
