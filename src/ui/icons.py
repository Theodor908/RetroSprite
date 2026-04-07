"""Phosphor icon to pixel art pipeline for RetroSprite toolbar."""

import os
import sys
import io
from PIL import Image
from src.ui.effects import colorize_icon, create_glow
from src.ui.theme import ACCENT_CYAN, ACCENT_PURPLE, hex_to_rgb

# Map tool names to Phosphor icon filenames (SVG preferred, PNG fallback)
TOOL_ICON_MAP = {
    "pen": "pen-bold.svg",
    "eraser": "eraser-bold.svg",
    "blur": "drop-bold.svg",
    "fill": "paint-bucket-bold.svg",
    "ellipse": "circle-bold.svg",
    "pick": "eyedropper-bold.svg",
    "select": "selection-bold.svg",
    "wand": "magic-wand-bold.svg",
    "line": "line-segment-bold.svg",
    "rect": "rectangle-bold.svg",
    "move": "arrows-out-cardinal-bold.svg",
    "hand": "hand-bold.svg",
    "lasso": "lasso-bold.svg",
    "polygon": "polygon-bold.svg",
    "roundrect": "cards-bold.svg",
    "text": "text-t-bold.svg",
}

# Non-tool icons used elsewhere in the UI
UI_ICON_MAP = {
    "stack": "stack-bold.svg",
}

# Also keep PNG fallback names
_PNG_FALLBACK = {
    "pen": "pen-bold.png",
    "eraser": "eraser-bold.png",
    "blur": "drop-bold.png",
    "fill": "paint-bucket-bold.png",
    "ellipse": "circle-bold.png",
    "pick": "eyedropper-bold.png",
    "select": "selection-bold.png",
    "wand": "magic-wand-bold.png",
    "line": "line-segment-bold.png",
    "rect": "rectangle-bold.png",
    "move": "arrows-out-cardinal-bold.png",
    "hand": "hand-bold.png",
    "lasso": "lasso-bold.png",
    "polygon": "polygon-bold.png",
    "roundrect": "cards-bold.png",
}

# Support both normal runs and PyInstaller bundles
if getattr(sys, 'frozen', False):
    _BASE = sys._MEIPASS
else:
    _BASE = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ICONS_DIR = os.path.join(_BASE, "icons")


def _load_svg(path: str) -> Image.Image | None:
    """Load an SVG file and return it as a PIL RGBA Image with transparent background."""
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM
        drawing = svg2rlg(path)
        if drawing:
            data = renderPM.drawToString(drawing, fmt='PNG', dpi=72)
            img = Image.open(io.BytesIO(data)).convert("RGBA")
            # reportlab renders with white bg — make white pixels transparent
            import numpy as np
            arr = np.array(img)
            # Pixels that are near-white (R>240, G>240, B>240) become transparent
            white_mask = (arr[:, :, 0] > 240) & (arr[:, :, 1] > 240) & (arr[:, :, 2] > 240)
            arr[white_mask, 3] = 0
            return Image.fromarray(arr, "RGBA")
    except Exception:
        pass
    return None


class IconPipeline:
    """Converts Phosphor icons into pixelated neon-themed toolbar icons."""

    def __init__(self, icon_size: int = 16, display_size: int = 32):
        self.icon_size = icon_size
        self.display_size = display_size
        self._cache = {}

    def prepare(self, source: Image.Image, line_color: tuple = (0, 240, 255)) -> Image.Image:
        """Resize source to display_size with smooth scaling, then colorize."""
        clean = source.convert("RGBA").resize(
            (self.display_size, self.display_size), Image.LANCZOS
        )
        colored = colorize_icon(clean, line_color, threshold=100)
        return colored

    def create_tool_icon(self, source: Image.Image,
                         line_color: tuple = (0, 240, 255)) -> tuple:
        """Create normal and glow variants of a tool icon."""
        normal = self.prepare(source, line_color)
        glow = create_glow(normal, line_color, radius=2, alpha=100)
        return normal, glow

    def get_icon(self, tool_name: str) -> tuple:
        """Get the pixelated icon for a tool. Tries SVG first, then PNG, then fallback."""
        if tool_name in self._cache:
            return self._cache[tool_name]

        # Try SVG first (check both tool and UI icon maps)
        svg_file = TOOL_ICON_MAP.get(tool_name) or UI_ICON_MAP.get(tool_name)
        if svg_file:
            svg_path = os.path.join(ICONS_DIR, svg_file)
            if os.path.exists(svg_path):
                source = _load_svg(svg_path)
                if source:
                    normal, glow = self.create_tool_icon(source)
                    self._cache[tool_name] = (normal, glow)
                    return normal, glow

        # Try PNG fallback
        png_file = _PNG_FALLBACK.get(tool_name)
        if png_file:
            png_path = os.path.join(ICONS_DIR, png_file)
            if os.path.exists(png_path):
                source = Image.open(png_path).convert("RGBA")
                normal, glow = self.create_tool_icon(source)
                self._cache[tool_name] = (normal, glow)
                return normal, glow

        # Letter fallback
        fallback = self._create_fallback(tool_name)
        self._cache[tool_name] = fallback
        return fallback

    def _create_fallback(self, tool_name: str) -> tuple:
        """Create a simple fallback icon when no source exists."""
        from PIL import ImageDraw
        size = self.display_size
        normal = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(normal)
        draw.rectangle([2, 2, size - 3, size - 3], outline=(0, 240, 255, 255), width=1)
        letter = tool_name[0].upper() if tool_name else "?"
        bbox = draw.textbbox((0, 0), letter)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((size - tw) // 2, (size - th) // 2), letter, fill=(0, 240, 255, 255))
        glow = create_glow(normal, (0, 240, 255), radius=2, alpha=100)
        return normal, glow
