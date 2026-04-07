"""Color palette management."""
from __future__ import annotations
import colorsys

RETRO_PALETTES = {
    "Pico-8": [
        (0, 0, 0, 255), (29, 43, 83, 255),
        (126, 37, 83, 255), (0, 135, 81, 255),
        (171, 82, 54, 255), (95, 87, 79, 255),
        (194, 195, 199, 255), (255, 241, 232, 255),
        (255, 0, 77, 255), (255, 163, 0, 255),
        (255, 236, 39, 255), (0, 228, 54, 255),
        (41, 173, 255, 255), (131, 118, 156, 255),
        (255, 119, 168, 255), (255, 204, 170, 255),
    ],
    "DB16": [
        (20, 12, 28, 255), (68, 36, 52, 255),
        (48, 52, 109, 255), (78, 74, 78, 255),
        (133, 76, 48, 255), (52, 101, 36, 255),
        (208, 70, 72, 255), (117, 113, 97, 255),
        (89, 125, 206, 255), (210, 125, 44, 255),
        (133, 149, 161, 255), (109, 170, 44, 255),
        (210, 170, 153, 255), (109, 194, 202, 255),
        (218, 212, 94, 255), (222, 238, 214, 255),
    ],
    "DB32": [
        (0, 0, 0, 255), (34, 32, 52, 255),
        (69, 40, 60, 255), (102, 57, 49, 255),
        (143, 86, 59, 255), (223, 113, 38, 255),
        (217, 160, 102, 255), (238, 195, 154, 255),
        (251, 242, 54, 255), (153, 229, 80, 255),
        (106, 190, 48, 255), (55, 148, 110, 255),
        (75, 105, 47, 255), (82, 75, 36, 255),
        (50, 60, 57, 255), (63, 63, 116, 255),
        (48, 96, 130, 255), (91, 110, 225, 255),
        (99, 155, 255, 255), (95, 205, 228, 255),
        (203, 219, 252, 255), (255, 255, 255, 255),
        (155, 173, 183, 255), (132, 126, 135, 255),
        (105, 106, 106, 255), (89, 86, 82, 255),
        (118, 110, 138, 255), (172, 50, 50, 255),
        (217, 87, 99, 255), (215, 123, 179, 255),
        (143, 151, 70, 255), (138, 111, 48, 255),
    ],
    "Commodore 64": [
        (0, 0, 0, 255), (255, 255, 255, 255),
        (137, 64, 54, 255), (122, 191, 199, 255),
        (138, 70, 174, 255), (104, 169, 65, 255),
        (62, 49, 162, 255), (208, 220, 113, 255),
        (144, 95, 37, 255), (92, 71, 0, 255),
        (187, 119, 109, 255), (85, 85, 85, 255),
        (128, 128, 128, 255), (172, 234, 136, 255),
        (124, 112, 218, 255), (171, 171, 171, 255),
    ],
    "NES": [
        (0, 0, 0, 255), (255, 255, 255, 255),
        (124, 124, 124, 255), (188, 188, 188, 255),
        (0, 0, 252, 255), (0, 120, 248, 255),
        (104, 136, 252, 255), (152, 120, 248, 255),
        (216, 0, 204, 255), (248, 56, 152, 255),
        (248, 120, 88, 255), (248, 184, 0, 255),
        (172, 124, 0, 255), (0, 184, 0, 255),
        (0, 168, 0, 255), (0, 168, 68, 255),
    ],
    "GameBoy": [
        (15, 56, 15, 255), (48, 98, 48, 255),
        (139, 172, 15, 255), (155, 188, 15, 255),
    ],
    "CGA": [
        (0, 0, 0, 255), (85, 255, 255, 255),
        (255, 85, 255, 255), (255, 255, 255, 255),
    ],
}


class Palette:
    def __init__(self, name: str = "Pico-8"):
        self.name = name
        self.colors: list[tuple[int, int, int, int]] = list(
            RETRO_PALETTES.get(name, RETRO_PALETTES["Pico-8"])
        )
        self.selected_index: int = 0

    @property
    def selected_color(self) -> tuple[int, int, int, int]:
        return self.colors[self.selected_index]

    def select(self, index: int) -> None:
        if 0 <= index < len(self.colors):
            self.selected_index = index

    def add_color(self, color: tuple[int, int, int, int]) -> None:
        if color not in self.colors:
            self.colors.append(color)

    def remove_color(self, index: int) -> None:
        """Remove color at index."""
        if 0 <= index < len(self.colors):
            self.colors.pop(index)
            if self.selected_index >= len(self.colors):
                self.selected_index = max(0, len(self.colors) - 1)

    def replace_color(self, index: int, color: tuple[int, int, int, int]) -> None:
        """Replace color at index."""
        if 0 <= index < len(self.colors):
            self.colors[index] = color

    def set_palette(self, name: str) -> None:
        if name in RETRO_PALETTES:
            self.name = name
            self.colors = list(RETRO_PALETTES[name])
            self.selected_index = 0


def generate_ramp(color1: tuple, color2: tuple, steps: int, mode: str = "rgb") -> list:
    """Interpolate between two colors to make a smooth ramp."""
    steps = max(2, min(32, steps))
    if mode == "hsv":
        return _ramp_hsv(color1, color2, steps)
    return _ramp_rgb(color1, color2, steps)


def _ramp_rgb(c1, c2, steps):
    result = []
    for i in range(steps):
        t = i / max(1, steps - 1)
        r = round(c1[0] + (c2[0] - c1[0]) * t)
        g = round(c1[1] + (c2[1] - c1[1]) * t)
        b = round(c1[2] + (c2[2] - c1[2]) * t)
        a = round(c1[3] + (c2[3] - c1[3]) * t)
        result.append((r, g, b, a))
    return result


def _ramp_hsv(c1, c2, steps):
    h1, s1, v1 = colorsys.rgb_to_hsv(c1[0] / 255, c1[1] / 255, c1[2] / 255)
    h2, s2, v2 = colorsys.rgb_to_hsv(c2[0] / 255, c2[1] / 255, c2[2] / 255)
    dh = h2 - h1
    if dh > 0.5:
        dh -= 1.0
    elif dh < -0.5:
        dh += 1.0
    result = []
    for i in range(steps):
        t = i / max(1, steps - 1)
        h = (h1 + dh * t) % 1.0
        s = s1 + (s2 - s1) * t
        v = v1 + (v2 - v1) * t
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        a = round(c1[3] + (c2[3] - c1[3]) * t)
        result.append((round(r * 255), round(g * 255), round(b * 255), a))
    return result
