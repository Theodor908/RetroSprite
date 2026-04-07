# tests/test_theme.py
import pytest
from src.ui.theme import (
    BG_DEEP, BG_PANEL, BG_PANEL_ALT, BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, ACCENT_MAGENTA, ACCENT_PURPLE,
    SUCCESS, WARNING,
    BUTTON_BG, BUTTON_HOVER, BUTTON_ACTIVE,
    NEON_GLOW_CYAN, NEON_GLOW_MAGENTA, NEON_GLOW_PURPLE,
    SCANLINE_DARK, SCANLINE_LIGHT,
    hex_to_rgb, rgb_to_hex, blend_color, dim_color
)


def test_hex_to_rgb():
    assert hex_to_rgb("#00f0ff") == (0, 240, 255)
    assert hex_to_rgb("#ff00aa") == (255, 0, 170)


def test_rgb_to_hex():
    assert rgb_to_hex(0, 240, 255) == "#00f0ff"


def test_blend_color():
    # 50% blend of black and white
    result = blend_color("#000000", "#ffffff", 0.5)
    r, g, b = hex_to_rgb(result)
    assert 126 <= r <= 128
    assert 126 <= g <= 128
    assert 126 <= b <= 128


def test_dim_color():
    result = dim_color("#00f0ff", 0.5)
    r, g, b = hex_to_rgb(result)
    assert r == 0
    assert g == 120
    assert b == 127  # floor(255*0.5)


def test_glow_constants_exist():
    assert NEON_GLOW_CYAN is not None
    assert NEON_GLOW_MAGENTA is not None
    assert NEON_GLOW_PURPLE is not None


def test_scanline_constants_exist():
    assert SCANLINE_DARK is not None
    assert SCANLINE_LIGHT is not None
