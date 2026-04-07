"""Built-in bitmap pixel fonts and text rendering for RetroSprite."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Tiny 3x5 font
# ---------------------------------------------------------------------------
# Each glyph is a list of 5 ints (one per row, top to bottom).
# Bit 2 (MSB of 3 bits) = leftmost pixel, bit 0 = rightmost pixel.
# Values are 0..7 (3 bits wide).
#
# Bit layout for a 3-wide glyph:
#   bit2  bit1  bit0
#    X     X     X
#
# So: 0b100=4 means only left pixel set,
#     0b010=2 means only middle pixel,
#     0b001=1 means only right pixel,
#     0b111=7 means all three pixels.

_TINY_GLYPHS: dict[str, list[int]] = {
    # ASCII 32 - space
    " ": [0, 0, 0, 0, 0],
    # ASCII 33 - !
    "!": [2, 2, 2, 0, 2],
    # ASCII 34 - "
    '"': [5, 5, 0, 0, 0],
    # ASCII 35 - #
    "#": [5, 7, 5, 7, 5],
    # ASCII 36 - $
    "$": [2, 6, 2, 3, 2],
    # ASCII 37 - %
    "%": [5, 1, 2, 4, 5],
    # ASCII 38 - &
    "&": [2, 5, 6, 5, 6],
    # ASCII 39 - '
    "'": [2, 2, 0, 0, 0],
    # ASCII 40 - (
    "(": [1, 2, 2, 2, 1],
    # ASCII 41 - )
    ")": [4, 2, 2, 2, 4],
    # ASCII 42 - *
    "*": [5, 2, 7, 2, 5],
    # ASCII 43 - +
    "+": [0, 2, 7, 2, 0],
    # ASCII 44 - ,
    ",": [0, 0, 0, 2, 4],
    # ASCII 45 - -
    "-": [0, 0, 7, 0, 0],
    # ASCII 46 - .
    ".": [0, 0, 0, 0, 2],
    # ASCII 47 - /
    "/": [1, 1, 2, 4, 4],
    # ASCII 48 - 0
    "0": [7, 5, 5, 5, 7],
    # ASCII 49 - 1
    "1": [2, 6, 2, 2, 7],
    # ASCII 50 - 2
    "2": [7, 1, 7, 4, 7],
    # ASCII 51 - 3
    "3": [7, 1, 7, 1, 7],
    # ASCII 52 - 4
    "4": [5, 5, 7, 1, 1],
    # ASCII 53 - 5
    "5": [7, 4, 7, 1, 7],
    # ASCII 54 - 6
    "6": [7, 4, 7, 5, 7],
    # ASCII 55 - 7
    "7": [7, 1, 1, 1, 1],
    # ASCII 56 - 8
    "8": [7, 5, 7, 5, 7],
    # ASCII 57 - 9
    "9": [7, 5, 7, 1, 7],
    # ASCII 58 - :
    ":": [0, 2, 0, 2, 0],
    # ASCII 59 - ;
    ";": [0, 2, 0, 2, 4],
    # ASCII 60 - <
    "<": [1, 2, 4, 2, 1],
    # ASCII 61 - =
    "=": [0, 7, 0, 7, 0],
    # ASCII 62 - >
    ">": [4, 2, 1, 2, 4],
    # ASCII 63 - ?
    "?": [7, 1, 2, 0, 2],
    # ASCII 64 - @
    "@": [7, 5, 7, 4, 7],
    # ASCII 65 - A
    "A": [2, 5, 7, 5, 5],
    # ASCII 66 - B
    "B": [6, 5, 6, 5, 6],
    # ASCII 67 - C
    "C": [7, 4, 4, 4, 7],
    # ASCII 68 - D
    "D": [6, 5, 5, 5, 6],
    # ASCII 69 - E
    "E": [7, 4, 6, 4, 7],
    # ASCII 70 - F
    "F": [7, 4, 6, 4, 4],
    # ASCII 71 - G
    "G": [7, 4, 5, 5, 7],
    # ASCII 72 - H
    "H": [5, 5, 7, 5, 5],
    # ASCII 73 - I
    "I": [7, 2, 2, 2, 7],
    # ASCII 74 - J
    "J": [7, 1, 1, 5, 7],
    # ASCII 75 - K
    "K": [5, 5, 6, 5, 5],
    # ASCII 76 - L
    "L": [4, 4, 4, 4, 7],
    # ASCII 77 - M
    "M": [5, 7, 5, 5, 5],
    # ASCII 78 - N
    "N": [5, 7, 7, 5, 5],
    # ASCII 79 - O
    "O": [7, 5, 5, 5, 7],
    # ASCII 80 - P
    "P": [7, 5, 7, 4, 4],
    # ASCII 81 - Q
    "Q": [7, 5, 5, 7, 1],
    # ASCII 82 - R
    "R": [6, 5, 6, 5, 5],
    # ASCII 83 - S
    "S": [7, 4, 7, 1, 7],
    # ASCII 84 - T
    "T": [7, 2, 2, 2, 2],
    # ASCII 85 - U
    "U": [5, 5, 5, 5, 7],
    # ASCII 86 - V
    "V": [5, 5, 5, 5, 2],
    # ASCII 87 - W
    "W": [5, 5, 5, 7, 5],
    # ASCII 88 - X
    "X": [5, 5, 2, 5, 5],
    # ASCII 89 - Y
    "Y": [5, 5, 2, 2, 2],
    # ASCII 90 - Z
    "Z": [7, 1, 2, 4, 7],
    # ASCII 91 - [
    "[": [3, 2, 2, 2, 3],
    # ASCII 92 - backslash
    "\\": [4, 4, 2, 1, 1],
    # ASCII 93 - ]
    "]": [6, 2, 2, 2, 6],
    # ASCII 94 - ^
    "^": [2, 5, 0, 0, 0],
    # ASCII 95 - _
    "_": [0, 0, 0, 0, 7],
    # ASCII 96 - `
    "`": [4, 2, 0, 0, 0],
    # ASCII 97 - a
    "a": [0, 6, 5, 5, 6],
    # ASCII 98 - b
    "b": [4, 6, 5, 5, 6],
    # ASCII 99 - c
    "c": [0, 3, 4, 4, 3],
    # ASCII 100 - d
    "d": [1, 3, 5, 5, 3],
    # ASCII 101 - e
    "e": [0, 7, 5, 4, 7],   # was 7,4,3 — adjusted
    # ASCII 102 - f
    "f": [3, 2, 7, 2, 2],
    # ASCII 103 - g
    "g": [0, 7, 5, 7, 1],
    # ASCII 104 - h
    "h": [4, 6, 5, 5, 5],
    # ASCII 105 - i
    "i": [2, 0, 2, 2, 2],
    # ASCII 106 - j
    "j": [1, 0, 1, 1, 6],
    # ASCII 107 - k
    "k": [4, 5, 6, 5, 5],
    # ASCII 108 - l
    "l": [6, 2, 2, 2, 7],
    # ASCII 109 - m
    "m": [0, 7, 7, 5, 5],
    # ASCII 110 - n
    "n": [0, 6, 5, 5, 5],
    # ASCII 111 - o
    "o": [0, 7, 5, 5, 7],
    # ASCII 112 - p
    "p": [0, 6, 5, 6, 4],
    # ASCII 113 - q
    "q": [0, 3, 5, 3, 1],
    # ASCII 114 - r
    "r": [0, 5, 6, 4, 4],
    # ASCII 115 - s
    "s": [0, 3, 6, 1, 6],
    # ASCII 116 - t
    "t": [2, 7, 2, 2, 1],
    # ASCII 117 - u
    "u": [0, 5, 5, 5, 3],
    # ASCII 118 - v
    "v": [0, 5, 5, 5, 2],
    # ASCII 119 - w
    "w": [0, 5, 5, 7, 5],
    # ASCII 120 - x
    "x": [0, 5, 2, 2, 5],
    # ASCII 121 - y
    "y": [0, 5, 5, 3, 1],
    # ASCII 122 - z
    "z": [0, 7, 2, 4, 7],
    # ASCII 123 - {
    "{": [3, 2, 6, 2, 3],
    # ASCII 124 - |
    "|": [2, 2, 2, 2, 2],
    # ASCII 125 - }
    "}": [6, 2, 3, 2, 6],
    # ASCII 126 - ~
    "~": [0, 6, 7, 3, 0],
}

FONT_TINY = {
    "name": "Tiny 3x5",
    "char_width": 3,
    "char_height": 5,
    "glyphs": _TINY_GLYPHS,
}

# ---------------------------------------------------------------------------
# Standard 5x7 font
# ---------------------------------------------------------------------------
# Each glyph is a list of 7 ints (one per row, top to bottom).
# Bit 4 (MSB of 5 bits) = leftmost pixel, bit 0 = rightmost pixel.
# Values are 0..31 (5 bits wide).
#
# Based on common 5x7 LED / HD44780 LCD patterns.

_STANDARD_GLYPHS: dict[str, list[int]] = {
    # ASCII 32 - space
    " ": [0, 0, 0, 0, 0, 0, 0],
    # ASCII 33 - !
    "!": [4, 4, 4, 4, 0, 0, 4],
    # ASCII 34 - "
    '"': [10, 10, 10, 0, 0, 0, 0],
    # ASCII 35 - #
    "#": [10, 10, 31, 10, 31, 10, 10],
    # ASCII 36 - $
    "$": [4, 15, 20, 14, 5, 30, 4],
    # ASCII 37 - %
    "%": [24, 25, 2, 4, 8, 19, 3],
    # ASCII 38 - &
    "&": [12, 18, 20, 8, 21, 18, 13],
    # ASCII 39 - '
    "'": [4, 4, 8, 0, 0, 0, 0],
    # ASCII 40 - (
    "(": [2, 4, 8, 8, 8, 4, 2],
    # ASCII 41 - )
    ")": [8, 4, 2, 2, 2, 4, 8],
    # ASCII 42 - *
    "*": [0, 4, 21, 14, 21, 4, 0],
    # ASCII 43 - +
    "+": [0, 4, 4, 31, 4, 4, 0],
    # ASCII 44 - ,
    ",": [0, 0, 0, 0, 12, 4, 8],
    # ASCII 45 - -
    "-": [0, 0, 0, 31, 0, 0, 0],
    # ASCII 46 - .
    ".": [0, 0, 0, 0, 0, 12, 12],
    # ASCII 47 - /
    "/": [1, 1, 2, 4, 8, 16, 16],
    # ASCII 48 - 0
    "0": [14, 17, 19, 21, 25, 17, 14],
    # ASCII 49 - 1
    "1": [4, 12, 4, 4, 4, 4, 14],
    # ASCII 50 - 2
    "2": [14, 17, 1, 6, 8, 16, 31],
    # ASCII 51 - 3
    "3": [31, 1, 2, 6, 1, 17, 14],
    # ASCII 52 - 4
    "4": [2, 6, 10, 18, 31, 2, 2],
    # ASCII 53 - 5
    "5": [31, 16, 30, 1, 1, 17, 14],
    # ASCII 54 - 6
    "6": [6, 8, 16, 30, 17, 17, 14],
    # ASCII 55 - 7
    "7": [31, 1, 2, 4, 8, 8, 8],
    # ASCII 56 - 8
    "8": [14, 17, 17, 14, 17, 17, 14],
    # ASCII 57 - 9
    "9": [14, 17, 17, 15, 1, 2, 12],
    # ASCII 58 - :
    ":": [0, 12, 12, 0, 12, 12, 0],
    # ASCII 59 - ;
    ";": [0, 12, 12, 0, 12, 4, 8],
    # ASCII 60 - <
    "<": [2, 4, 8, 16, 8, 4, 2],
    # ASCII 61 - =
    "=": [0, 0, 31, 0, 31, 0, 0],
    # ASCII 62 - >
    ">": [8, 4, 2, 1, 2, 4, 8],
    # ASCII 63 - ?
    "?": [14, 17, 1, 6, 4, 0, 4],
    # ASCII 64 - @
    "@": [14, 17, 1, 13, 21, 21, 14],
    # ASCII 65 - A
    "A": [4, 10, 17, 17, 31, 17, 17],
    # ASCII 66 - B
    "B": [30, 17, 17, 30, 17, 17, 30],
    # ASCII 67 - C
    "C": [14, 17, 16, 16, 16, 17, 14],
    # ASCII 68 - D
    "D": [28, 18, 17, 17, 17, 18, 28],
    # ASCII 69 - E
    "E": [31, 16, 16, 30, 16, 16, 31],
    # ASCII 70 - F
    "F": [31, 16, 16, 30, 16, 16, 16],
    # ASCII 71 - G
    "G": [14, 17, 16, 16, 19, 17, 14],
    # ASCII 72 - H
    "H": [17, 17, 17, 31, 17, 17, 17],
    # ASCII 73 - I
    "I": [14, 4, 4, 4, 4, 4, 14],
    # ASCII 74 - J
    "J": [7, 2, 2, 2, 2, 18, 12],
    # ASCII 75 - K
    "K": [17, 18, 20, 24, 20, 18, 17],
    # ASCII 76 - L
    "L": [16, 16, 16, 16, 16, 16, 31],
    # ASCII 77 - M
    "M": [17, 27, 21, 21, 17, 17, 17],
    # ASCII 78 - N
    "N": [17, 17, 25, 21, 19, 17, 17],
    # ASCII 79 - O
    "O": [14, 17, 17, 17, 17, 17, 14],
    # ASCII 80 - P
    "P": [30, 17, 17, 30, 16, 16, 16],
    # ASCII 81 - Q
    "Q": [14, 17, 17, 17, 21, 18, 13],
    # ASCII 82 - R
    "R": [30, 17, 17, 30, 20, 18, 17],
    # ASCII 83 - S
    "S": [14, 17, 16, 14, 1, 17, 14],
    # ASCII 84 - T
    "T": [31, 4, 4, 4, 4, 4, 4],
    # ASCII 85 - U
    "U": [17, 17, 17, 17, 17, 17, 14],
    # ASCII 86 - V
    "V": [17, 17, 17, 17, 17, 10, 4],
    # ASCII 87 - W
    "W": [17, 17, 17, 21, 21, 21, 10],
    # ASCII 88 - X
    "X": [17, 17, 10, 4, 10, 17, 17],
    # ASCII 89 - Y
    "Y": [17, 17, 10, 4, 4, 4, 4],
    # ASCII 90 - Z
    "Z": [31, 1, 2, 4, 8, 16, 31],
    # ASCII 91 - [
    "[": [7, 4, 4, 4, 4, 4, 7],
    # ASCII 92 - backslash
    "\\": [16, 16, 8, 4, 2, 1, 1],
    # ASCII 93 - ]
    "]": [28, 4, 4, 4, 4, 4, 28],
    # ASCII 94 - ^
    "^": [4, 10, 17, 0, 0, 0, 0],
    # ASCII 95 - _
    "_": [0, 0, 0, 0, 0, 0, 31],
    # ASCII 96 - `
    "`": [8, 4, 2, 0, 0, 0, 0],
    # ASCII 97 - a
    "a": [0, 0, 14, 1, 15, 17, 15],
    # ASCII 98 - b
    "b": [16, 16, 30, 17, 17, 17, 30],
    # ASCII 99 - c
    "c": [0, 0, 14, 16, 16, 17, 14],
    # ASCII 100 - d
    "d": [1, 1, 15, 17, 17, 17, 15],
    # ASCII 101 - e
    "e": [0, 0, 14, 17, 31, 16, 14],
    # ASCII 102 - f
    "f": [6, 9, 8, 28, 8, 8, 8],
    # ASCII 103 - g
    "g": [0, 15, 17, 17, 15, 1, 14],
    # ASCII 104 - h
    "h": [16, 16, 22, 25, 17, 17, 17],
    # ASCII 105 - i
    "i": [4, 0, 12, 4, 4, 4, 14],
    # ASCII 106 - j
    "j": [2, 0, 6, 2, 2, 18, 12],
    # ASCII 107 - k
    "k": [16, 16, 18, 20, 24, 20, 18],
    # ASCII 108 - l
    "l": [12, 4, 4, 4, 4, 4, 14],
    # ASCII 109 - m
    "m": [0, 0, 26, 21, 21, 17, 17],
    # ASCII 110 - n
    "n": [0, 0, 22, 25, 17, 17, 17],
    # ASCII 111 - o
    "o": [0, 0, 14, 17, 17, 17, 14],
    # ASCII 112 - p
    "p": [0, 30, 17, 17, 30, 16, 16],
    # ASCII 113 - q
    "q": [0, 15, 17, 17, 15, 1, 1],
    # ASCII 114 - r
    "r": [0, 0, 22, 25, 16, 16, 16],
    # ASCII 115 - s
    "s": [0, 0, 14, 16, 14, 1, 30],
    # ASCII 116 - t
    "t": [8, 8, 28, 8, 8, 9, 6],
    # ASCII 117 - u
    "u": [0, 0, 17, 17, 17, 19, 13],
    # ASCII 118 - v
    "v": [0, 0, 17, 17, 17, 10, 4],
    # ASCII 119 - w
    "w": [0, 0, 17, 21, 21, 21, 10],
    # ASCII 120 - x
    "x": [0, 0, 17, 10, 4, 10, 17],
    # ASCII 121 - y
    "y": [0, 17, 17, 15, 1, 17, 14],
    # ASCII 122 - z
    "z": [0, 0, 31, 2, 4, 8, 31],
    # ASCII 123 - {
    "{": [3, 4, 4, 8, 4, 4, 3],
    # ASCII 124 - |
    "|": [4, 4, 4, 4, 4, 4, 4],
    # ASCII 125 - }
    "}": [24, 4, 4, 2, 4, 4, 24],
    # ASCII 126 - ~
    "~": [0, 8, 21, 2, 0, 0, 0],
}

FONT_STANDARD = {
    "name": "Standard 5x7",
    "char_width": 5,
    "char_height": 7,
    "glyphs": _STANDARD_GLYPHS,
}

# ---------------------------------------------------------------------------
# Public registry
# ---------------------------------------------------------------------------

FONTS: list[dict] = [FONT_TINY, FONT_STANDARD]


# ---------------------------------------------------------------------------
# Text rendering
# ---------------------------------------------------------------------------

def render_text(text: str, font: dict, color: tuple,
                spacing: int = 1, line_height: int = 2,
                align: str = "left") -> Image.Image:
    """Render text using a built-in bitmap font.

    Args:
        text: String to render (supports newlines)
        font: Font dict with 'char_width', 'char_height', 'glyphs'
        color: RGBA color tuple for text pixels
        spacing: Extra pixels between characters
        line_height: Extra pixels between lines
        align: 'left', 'center', or 'right'

    Returns:
        RGBA PIL Image with rendered text
    """
    if not text:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

    cw = font["char_width"]
    ch = font["char_height"]
    glyphs = font["glyphs"]
    lines = text.split("\n")

    def _line_width(line):
        if not line:
            return 0
        return len(line) * cw + (len(line) - 1) * spacing

    line_widths = [_line_width(line) for line in lines]
    img_w = max(line_widths) if line_widths else 1
    img_h = len(lines) * ch + (len(lines) - 1) * line_height
    if img_w <= 0:
        img_w = 1
    if img_h <= 0:
        img_h = 1

    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    pixels = np.array(img)

    for row_idx, line in enumerate(lines):
        y_off = row_idx * (ch + line_height)
        lw = line_widths[row_idx]
        if align == "center":
            x_start = (img_w - lw) // 2
        elif align == "right":
            x_start = img_w - lw
        else:
            x_start = 0

        for col_idx, char in enumerate(line):
            glyph = glyphs.get(char)
            if glyph is None:
                glyph = [(1 << cw) - 1] * ch

            cx = x_start + col_idx * (cw + spacing)
            for gy, row_bits in enumerate(glyph):
                for gx in range(cw):
                    if row_bits & (1 << (cw - 1 - gx)):
                        px, py = cx + gx, y_off + gy
                        if 0 <= px < img_w and 0 <= py < img_h:
                            pixels[py, px] = color

    return Image.fromarray(pixels, "RGBA")


def get_cursor_x(text: str, cursor_pos: int, font: dict, spacing: int = 1) -> int:
    """Calculate pixel X offset of cursor at given character index."""
    cw = font["char_width"]
    lines = text.split("\n")
    pos = cursor_pos
    for line in lines:
        if pos <= len(line):
            if pos == 0:
                return 0
            if pos == len(line) and len(line) > 0:
                # End of line: right edge of last character (no trailing spacing)
                return len(line) * cw + (len(line) - 1) * spacing
            return pos * (cw + spacing)
        pos -= len(line) + 1
    last_line = lines[-1] if lines else ""
    if not last_line:
        return 0
    return len(last_line) * cw + (len(last_line) - 1) * spacing


def render_text_ttf(text: str, font_path: str, size: int, color: tuple,
                    spacing: int = 0, line_height: int = 0,
                    align: str = "left") -> Image.Image:
    """Render text using a TTF font via Pillow.

    Renders as crisp 1-bit pixels (no anti-aliasing) suitable for pixel art.
    The text is drawn to a grayscale mask, thresholded to binary, then
    colored with the user's chosen color.
    """
    if not text:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

    font = ImageFont.truetype(font_path, size)
    ascent, descent = font.getmetrics()
    row_h = ascent + descent  # Full line height including descenders
    lines = text.split("\n")

    line_widths = []
    for line in lines:
        if not line:
            line_widths.append(0)
            continue
        if spacing > 0:
            w = 0
            for ch in line:
                bbox = font.getbbox(ch)
                w += (bbox[2] - bbox[0]) + spacing
            w -= spacing  # No trailing spacing
            line_widths.append(w)
        else:
            bbox = font.getbbox(line)
            line_widths.append(bbox[2] - bbox[0])

    img_w = max(line_widths) if line_widths else 1
    total_h = len(lines) * row_h + line_height * max(0, len(lines) - 1)
    if img_w <= 0:
        img_w = 1
    if total_h <= 0:
        total_h = 1

    # Render to grayscale mask first (white on black)
    mask = Image.new("L", (img_w, total_h), 0)
    draw = ImageDraw.Draw(mask)

    y = 0
    for i, line in enumerate(lines):
        if not line:
            y += row_h + line_height
            continue
        lw = line_widths[i]
        if align == "center":
            x = (img_w - lw) // 2
        elif align == "right":
            x = img_w - lw
        else:
            x = 0

        if spacing > 0:
            cx = x
            for ch in line:
                draw.text((cx, y), ch, fill=255, font=font)
                bbox = font.getbbox(ch)
                cx += (bbox[2] - bbox[0]) + spacing
        else:
            draw.text((x, y), line, fill=255, font=font)

        y += row_h + line_height

    # Threshold to binary and apply user color
    mask_arr = np.array(mask)
    h, w = mask_arr.shape
    result = np.zeros((h, w, 4), dtype=np.uint8)
    opaque = mask_arr > 127  # Binary threshold — no anti-aliasing
    result[opaque] = color

    return Image.fromarray(result, "RGBA")
