# UI Overhaul & Animation Timeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform RetroSprite from a flat dark UI with text buttons into a full cyberpunk neon pixel art editor with an Aseprite-style bottom timeline.

**Architecture:** Bottom-up build — theme/effects foundation first, then new components (icons, options bar, timeline), then rewrites (toolbar, right panel), then app.py assembly. Each task is independently testable.

**Tech Stack:** Python 3.8+, Tkinter, Pillow (PIL), NumPy

---

## Phase 1: Foundation (Theme + Effects + Model Updates)

### Task 1: Update Theme Constants & Style Helpers

**Files:**
- Modify: `src/ui/theme.py:1-106`
- Test: `tests/test_theme.py` (create)

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_theme.py -v`
Expected: FAIL — new constants and functions don't exist yet

**Step 3: Implement theme updates**

Add to `src/ui/theme.py` after line 17:

```python
# Neon glow variants (softer/transparent versions for glow effects)
NEON_GLOW_CYAN = "#00f0ff"      # Same as ACCENT_CYAN, used at reduced opacity in PIL
NEON_GLOW_MAGENTA = "#ff00aa"   # Same as ACCENT_MAGENTA
NEON_GLOW_PURPLE = "#8b5cf6"    # Same as ACCENT_PURPLE

# Scanline effect colors
SCANLINE_DARK = "#0a0a10"
SCANLINE_LIGHT = "#12121c"

# Onion skin tints
ONION_PAST_TINT = "#ff006640"    # Magenta with alpha (as hex for reference)
ONION_FUTURE_TINT = "#00f0ff40"  # Cyan with alpha


def hex_to_rgb(hex_color: str) -> tuple:
    """Convert '#RRGGBB' to (R, G, B) tuple."""
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert (R, G, B) to '#rrggbb' string."""
    return f"#{r:02x}{g:02x}{b:02x}"


def blend_color(color1: str, color2: str, t: float) -> str:
    """Blend two hex colors. t=0 returns color1, t=1 returns color2."""
    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return rgb_to_hex(r, g, b)


def dim_color(color: str, factor: float) -> str:
    """Dim a hex color by a factor (0.0=black, 1.0=unchanged)."""
    r, g, b = hex_to_rgb(color)
    return rgb_to_hex(int(r * factor), int(g * factor), int(b * factor))
```

Also fix the `style_canvas` dead branch at line 95-98: change so `is_main=True` uses `BG_DEEP` and `is_main=False` uses `BG_PANEL_ALT`.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_theme.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/ui/theme.py tests/test_theme.py
git commit -m "feat(theme): add color utility functions and glow/scanline constants"
```

---

### Task 2: Create Effects Module

**Files:**
- Create: `src/ui/effects.py`
- Test: `tests/test_effects.py` (create)

**Step 1: Write the failing test**

```python
# tests/test_effects.py
import pytest
from PIL import Image
from src.ui.effects import create_glow, create_scanline_texture, colorize_icon


def test_create_glow_returns_rgba():
    # 8x8 white square on transparent background
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    img.paste((255, 255, 255, 255), (2, 2, 6, 6))
    result = create_glow(img, (0, 240, 255), radius=1)
    assert result.mode == "RGBA"
    assert result.size == (8, 8)


def test_create_glow_expands_non_transparent():
    img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    # Single pixel at center
    img.putpixel((5, 5), (255, 255, 255, 255))
    result = create_glow(img, (0, 240, 255), radius=1)
    # The glow should make neighboring pixels non-transparent
    neighbor = result.getpixel((5, 6))
    assert neighbor[3] > 0  # alpha > 0


def test_colorize_icon():
    # Grayscale icon: white lines on black bg
    img = Image.new("RGBA", (4, 4), (0, 0, 0, 255))
    img.putpixel((1, 1), (255, 255, 255, 255))
    result = colorize_icon(img, line_color=(0, 240, 255), threshold=128)
    assert result.mode == "RGBA"
    # The white pixel should now be cyan
    px = result.getpixel((1, 1))
    assert px[0] == 0 and px[1] == 240 and px[2] == 255 and px[3] == 255
    # The black pixel should be transparent
    bg = result.getpixel((0, 0))
    assert bg[3] == 0


def test_create_scanline_texture():
    result = create_scanline_texture(20, 10, "#0a0a10", "#12121c")
    assert result.mode == "RGBA"
    assert result.size == (20, 10)
    # Even rows should differ from odd rows
    px_even = result.getpixel((0, 0))
    px_odd = result.getpixel((0, 1))
    assert px_even != px_odd
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_effects.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Implement effects module**

```python
# src/ui/effects.py
"""Cyberpunk neon visual effects for RetroSprite UI."""

from PIL import Image, ImageFilter
from src.ui.theme import hex_to_rgb


def create_glow(img: Image.Image, color: tuple, radius: int = 2, alpha: int = 80) -> Image.Image:
    """Add a soft colored glow around non-transparent pixels in an RGBA image."""
    glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    # Extract alpha channel, blur it to create glow mask
    alpha_channel = img.split()[3]
    blurred = alpha_channel.filter(ImageFilter.GaussianBlur(radius=radius))
    # Create colored glow from blurred alpha
    r, g, b = color
    glow_data = []
    blur_data = list(blurred.getdata())
    for a in blur_data:
        glow_alpha = min(alpha, a)
        glow_data.append((r, g, b, glow_alpha))
    glow_layer.putdata(glow_data)
    # Composite: glow behind original
    result = Image.alpha_composite(glow_layer, img)
    return result


def colorize_icon(img: Image.Image, line_color: tuple, threshold: int = 128,
                  fill_color: tuple = None) -> Image.Image:
    """Convert a grayscale icon to neon-colored with transparent background.

    Pixels brighter than threshold become line_color, darker become transparent.
    If fill_color is provided, mid-range pixels get that color.
    """
    result = Image.new("RGBA", img.size, (0, 0, 0, 0))
    pixels = img.load()
    result_pixels = result.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            px = pixels[x, y]
            # Handle both RGBA and RGB
            if len(px) == 4:
                r, g, b, a = px
            else:
                r, g, b = px
                a = 255
            brightness = (r + g + b) // 3
            if a < 32:
                continue  # Already transparent
            if brightness >= threshold:
                result_pixels[x, y] = (*line_color, 255)
            elif fill_color and brightness >= threshold // 2:
                result_pixels[x, y] = (*fill_color, 180)
            # else: stays transparent
    return result


def create_scanline_texture(width: int, height: int,
                            dark_color: str, light_color: str) -> Image.Image:
    """Create a CRT scanline texture overlay."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    dark_rgb = hex_to_rgb(dark_color)
    light_rgb = hex_to_rgb(light_color)
    pixels = img.load()
    for y in range(height):
        color = dark_rgb if y % 2 == 0 else light_rgb
        for x in range(width):
            pixels[x, y] = (*color, 30)  # Very subtle alpha
    return img


def gradient_line_colors(color1: str, color2: str, steps: int) -> list:
    """Generate a list of hex colors forming a gradient between two colors."""
    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)
    colors = []
    for i in range(steps):
        t = i / max(1, steps - 1)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        from src.ui.theme import rgb_to_hex
        colors.append(rgb_to_hex(r, g, b))
    return colors
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_effects.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/ui/effects.py tests/test_effects.py
git commit -m "feat(effects): add glow, colorize, scanline, and gradient utilities"
```

---

### Task 3: Add Per-Frame Duration to Animation Model

**Files:**
- Modify: `src/animation.py:7-15` (Frame class) and `src/animation.py:68-75` (AnimationTimeline)
- Test: `tests/test_animation.py` (existing — add new tests)

**Step 1: Write the failing test**

```python
# Add to tests/test_animation.py
def test_frame_default_duration():
    frame = Frame(16, 16)
    assert frame.duration_ms == 100


def test_frame_custom_duration():
    frame = Frame(16, 16)
    frame.duration_ms = 200
    assert frame.duration_ms == 200


def test_timeline_per_frame_durations():
    tl = AnimationTimeline(16, 16)
    tl.add_frame()  # frame 2
    tl.current_frame_obj().duration_ms = 200
    tl.set_current(0)
    assert tl.current_frame_obj().duration_ms == 100
    tl.set_current(1)
    assert tl.current_frame_obj().duration_ms == 200


def test_frame_copy_preserves_duration():
    frame = Frame(16, 16)
    frame.duration_ms = 250
    copied = frame.copy()
    assert copied.duration_ms == 250
```

Note: `current_frame_obj()` is a new method that returns the Frame object (not the flattened PixelGrid).

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_animation.py -v -k "duration"`
Expected: FAIL — `duration_ms` attribute doesn't exist

**Step 3: Implement per-frame duration**

In `src/animation.py`, modify `Frame.__init__` (line 10-15):
- Add `self.duration_ms = 100` after line 15

In `Frame.copy()` method: add `new_frame.duration_ms = self.duration_ms` before the return.

In `AnimationTimeline` class, add method:
```python
def current_frame_obj(self) -> Frame:
    """Return the current Frame object (not flattened)."""
    return self._frames[self._current_index]
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_animation.py -v -k "duration"`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/animation.py tests/test_animation.py
git commit -m "feat(animation): add per-frame duration_ms to Frame model"
```

---

### Task 4: Enhance Onion Skin Model (Multi-Frame + Color Tint)

**Files:**
- Modify: `src/canvas.py:9-58` (build_render_image)
- Test: `tests/test_canvas.py` (existing — add new tests)

**Step 1: Write the failing test**

```python
# Add to tests/test_canvas.py (or create if needed)
from src.canvas import build_render_image
from src.pixel_data import PixelGrid
import numpy as np


def test_onion_skin_multi_frame():
    """build_render_image accepts onion_grids list instead of single onion_grid."""
    grid = PixelGrid(8, 8)
    past_1 = PixelGrid(8, 8)
    past_1.set_pixel(0, 0, (255, 0, 0, 255))
    past_2 = PixelGrid(8, 8)
    past_2.set_pixel(1, 1, (0, 255, 0, 255))

    # New signature: onion_past_grids, onion_future_grids
    img = build_render_image(
        grid, 8, 8, pixel_size=1,
        onion_past_grids=[past_1, past_2],
        onion_future_grids=[],
        onion_past_tint=(255, 0, 170),
        onion_future_tint=(0, 240, 255)
    )
    assert img is not None
    assert img.size == (8, 8)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_canvas.py::test_onion_skin_multi_frame -v`
Expected: FAIL — new parameters not accepted

**Step 3: Update build_render_image signature**

Modify `src/canvas.py` `build_render_image` (line 9) to accept new onion skin parameters while keeping backward compatibility with the old `onion_grid` parameter:

```python
def build_render_image(pixel_grid, width, height, pixel_size=16,
                       show_grid=False,
                       onion_grid=None,  # DEPRECATED: kept for backward compat
                       onion_past_grids=None,
                       onion_future_grids=None,
                       onion_past_tint=(255, 0, 170),
                       onion_future_tint=(0, 240, 255),
                       reference_image=None,
                       reference_opacity=0.3):
```

In the body, if `onion_grid` is provided but `onion_past_grids` is not, wrap it: `onion_past_grids = [onion_grid]`.

Then render each past grid with decreasing opacity (e.g., 64 for nearest, 32 for next, etc.) tinted with `onion_past_tint`. Same for future grids tinted with `onion_future_tint`.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_canvas.py -v`
Expected: All PASS (including existing onion skin tests using old `onion_grid` param)

**Step 5: Commit**

```bash
git add src/canvas.py tests/test_canvas.py
git commit -m "feat(canvas): multi-frame onion skinning with color tinting"
```

---

### Task 5: Create Icon Pipeline

**Files:**
- Create: `src/ui/icons.py`
- Create: `icons/` directory with Phosphor PNGs
- Test: `tests/test_icons.py` (create)

**Step 1: Write the failing test**

```python
# tests/test_icons.py
import pytest
from PIL import Image
from src.ui.icons import IconPipeline


def test_pipeline_pixelate():
    pipeline = IconPipeline(icon_size=16, display_size=32)
    # Create a simple test icon (white circle on black)
    src = Image.new("RGBA", (64, 64), (0, 0, 0, 255))
    result = pipeline.pixelate(src, line_color=(0, 240, 255))
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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_icons.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Implement icon pipeline**

```python
# src/ui/icons.py
"""Phosphor icon to pixel art pipeline for RetroSprite toolbar."""

import os
from PIL import Image
from src.ui.effects import colorize_icon, create_glow
from src.ui.theme import ACCENT_CYAN, ACCENT_PURPLE, hex_to_rgb

# Map tool names to Phosphor icon filenames
TOOL_ICON_MAP = {
    "pen": "pen.png",
    "eraser": "eraser.png",
    "blur": "drop.png",
    "fill": "paint-bucket.png",
    "ellipse": "circle.png",
    "pick": "eyedropper.png",
    "select": "selection.png",
    "wand": "magic-wand.png",
    "line": "line-segment.png",
    "rect": "rectangle.png",
    "hand": "hand.png",
}

ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "icons")


class IconPipeline:
    """Converts Phosphor icons into pixelated neon-themed toolbar icons."""

    def __init__(self, icon_size: int = 16, display_size: int = 32):
        self.icon_size = icon_size
        self.display_size = display_size
        self._cache = {}

    def pixelate(self, source: Image.Image, line_color: tuple = (0, 240, 255),
                 fill_color: tuple = None) -> Image.Image:
        """Downscale source to icon_size, colorize, upscale to display_size."""
        # Downscale with LANCZOS for good detail preservation
        small = source.convert("RGBA").resize(
            (self.icon_size, self.icon_size), Image.LANCZOS
        )
        # Colorize: threshold to neon lines on transparent bg
        colored = colorize_icon(small, line_color, threshold=100, fill_color=fill_color)
        # Upscale with NEAREST for crisp pixel look
        result = colored.resize(
            (self.display_size, self.display_size), Image.NEAREST
        )
        return result

    def create_tool_icon(self, source: Image.Image,
                         line_color: tuple = (0, 240, 255)) -> tuple:
        """Create normal and glow variants of a tool icon.
        Returns (normal_img, glow_img) as PIL RGBA images.
        """
        normal = self.pixelate(source, line_color)
        glow = create_glow(normal, line_color, radius=2, alpha=100)
        return normal, glow

    def get_icon(self, tool_name: str) -> Image.Image:
        """Get the pixelated icon for a tool. Returns fallback if not found."""
        if tool_name in self._cache:
            return self._cache[tool_name]

        filename = TOOL_ICON_MAP.get(tool_name)
        icon_path = os.path.join(ICONS_DIR, filename) if filename else None

        if icon_path and os.path.exists(icon_path):
            source = Image.open(icon_path)
            normal, glow = self.create_tool_icon(source)
            self._cache[tool_name] = (normal, glow)
            return normal, glow
        else:
            # Fallback: generate a simple colored square with first letter
            fallback = self._create_fallback(tool_name)
            self._cache[tool_name] = fallback
            return fallback

    def _create_fallback(self, tool_name: str) -> tuple:
        """Create a simple fallback icon (colored square) when no source PNG exists."""
        from PIL import ImageDraw, ImageFont
        size = self.display_size
        normal = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(normal)
        # Draw a neon border rectangle
        draw.rectangle([2, 2, size - 3, size - 3], outline=(0, 240, 255, 255), width=1)
        # Draw first letter centered
        letter = tool_name[0].upper() if tool_name else "?"
        bbox = draw.textbbox((0, 0), letter)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((size - tw) // 2, (size - th) // 2), letter, fill=(0, 240, 255, 255))
        glow = create_glow(normal, (0, 240, 255), radius=2, alpha=100)
        return normal, glow
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_icons.py -v`
Expected: All PASS

**Step 5: Create icons directory**

```bash
mkdir -p icons
```

**Step 6: Commit**

```bash
git add src/ui/icons.py tests/test_icons.py icons/
git commit -m "feat(icons): add Phosphor-to-pixel icon pipeline with glow variants"
```

---

## Phase 2: New UI Components

### Task 6: Create Top Options Bar

**Files:**
- Create: `src/ui/options_bar.py`
- Test: `tests/test_options_bar.py` (create)

**Step 1: Write the failing test**

```python
# tests/test_options_bar.py
import pytest
import tkinter as tk
from src.ui.options_bar import OptionsBar


@pytest.fixture
def root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def test_options_bar_creation(root):
    bar = OptionsBar(root)
    assert bar is not None
    assert bar.winfo_exists()


def test_options_bar_update_tool(root):
    bar = OptionsBar(root)
    bar.set_tool("pen")
    assert bar.current_tool == "pen"
    # Pen should show size, symmetry, dither, pixel perfect
    assert bar._size_frame.winfo_ismapped() or bar._size_frame.winfo_manager() != ""


def test_options_bar_update_tool_hand(root):
    bar = OptionsBar(root)
    bar.set_tool("hand")
    assert bar.current_tool == "hand"
    # Hand should hide size controls


def test_options_bar_get_size(root):
    bar = OptionsBar(root)
    bar.set_tool("pen")
    bar.set_size(5)
    assert bar.get_size() == 5


def test_options_bar_get_symmetry(root):
    bar = OptionsBar(root)
    assert bar.get_symmetry() == "off"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_options_bar.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Implement options bar**

```python
# src/ui/options_bar.py
"""Top context-sensitive tool options bar for RetroSprite."""

import tkinter as tk
from src.ui.theme import (
    BG_PANEL, BG_PANEL_ALT, BG_DEEP, BORDER, ACCENT_CYAN, ACCENT_MAGENTA,
    TEXT_PRIMARY, TEXT_SECONDARY, BUTTON_BG, BUTTON_HOVER,
    style_button, style_label, style_frame
)

# Which tools show which controls
TOOL_OPTIONS = {
    "pen":     {"size": True, "symmetry": True, "dither": True, "pixel_perfect": True},
    "eraser":  {"size": True, "symmetry": True, "dither": True, "pixel_perfect": True},
    "blur":    {"size": True},
    "fill":    {"tolerance": True, "dither": True},
    "ellipse": {"size": True, "symmetry": True},
    "pick":    {},
    "select":  {},
    "wand":    {"tolerance": True},
    "line":    {"size": True, "symmetry": True},
    "rect":    {"size": True, "symmetry": True},
    "hand":    {},
}


class OptionsBar(tk.Frame):
    """Context-sensitive tool options bar displayed below the menu bar."""

    def __init__(self, parent, on_size_change=None, on_symmetry_change=None,
                 on_dither_change=None, on_pixel_perfect_toggle=None,
                 on_tolerance_change=None):
        super().__init__(parent, bg=BG_PANEL, height=36)
        self.pack_propagate(False)

        self.current_tool = "pen"
        self._on_size_change = on_size_change
        self._on_symmetry_change = on_symmetry_change
        self._on_dither_change = on_dither_change
        self._on_pixel_perfect_toggle = on_pixel_perfect_toggle
        self._on_tolerance_change = on_tolerance_change

        # Tool indicator
        self._tool_label = tk.Label(self, text="Pen", font=("Consolas", 9, "bold"),
                                    bg=BG_PANEL, fg=ACCENT_CYAN)
        self._tool_label.pack(side="left", padx=(8, 16))

        # Separator
        sep = tk.Frame(self, width=1, bg=ACCENT_CYAN)
        sep.pack(side="left", fill="y", pady=4)

        # Size controls
        self._size_frame = tk.Frame(self, bg=BG_PANEL)
        tk.Label(self._size_frame, text="Size:", font=("Consolas", 8),
                 bg=BG_PANEL, fg=TEXT_SECONDARY).pack(side="left", padx=(8, 2))
        self._size_var = tk.IntVar(value=1)
        btn_minus = tk.Button(self._size_frame, text="-", width=2, font=("Consolas", 8),
                              bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                              command=lambda: self._change_size(-1))
        btn_minus.pack(side="left")
        self._size_label = tk.Label(self._size_frame, textvariable=self._size_var,
                                    font=("Consolas", 9, "bold"), bg=BG_PANEL, fg=TEXT_PRIMARY,
                                    width=3)
        self._size_label.pack(side="left")
        btn_plus = tk.Button(self._size_frame, text="+", width=2, font=("Consolas", 8),
                             bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                             command=lambda: self._change_size(1))
        btn_plus.pack(side="left")

        # Symmetry dropdown
        self._sym_frame = tk.Frame(self, bg=BG_PANEL)
        tk.Label(self._sym_frame, text="Sym:", font=("Consolas", 8),
                 bg=BG_PANEL, fg=TEXT_SECONDARY).pack(side="left", padx=(8, 2))
        self._sym_var = tk.StringVar(value="off")
        self._sym_options = ["off", "horizontal", "vertical", "both"]
        self._sym_btn = tk.Button(self._sym_frame, textvariable=self._sym_var,
                                  width=8, font=("Consolas", 8),
                                  bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                                  command=self._cycle_symmetry)
        self._sym_btn.pack(side="left")

        # Dither dropdown
        self._dither_frame = tk.Frame(self, bg=BG_PANEL)
        tk.Label(self._dither_frame, text="Dither:", font=("Consolas", 8),
                 bg=BG_PANEL, fg=TEXT_SECONDARY).pack(side="left", padx=(8, 2))
        self._dither_var = tk.StringVar(value="none")
        self._dither_btn = tk.Button(self._dither_frame, textvariable=self._dither_var,
                                     width=8, font=("Consolas", 8),
                                     bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                                     command=self._cycle_dither)
        self._dither_btn.pack(side="left")

        # Pixel Perfect toggle
        self._pp_frame = tk.Frame(self, bg=BG_PANEL)
        self._pp_var = tk.BooleanVar(value=False)
        self._pp_btn = tk.Button(self._pp_frame, text="PP: Off", width=6,
                                 font=("Consolas", 8),
                                 bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                                 command=self._toggle_pp)
        self._pp_btn.pack(side="left", padx=(8, 0))

        # Tolerance controls
        self._tol_frame = tk.Frame(self, bg=BG_PANEL)
        tk.Label(self._tol_frame, text="Tol:", font=("Consolas", 8),
                 bg=BG_PANEL, fg=TEXT_SECONDARY).pack(side="left", padx=(8, 2))
        self._tol_var = tk.IntVar(value=32)
        tk.Button(self._tol_frame, text="-", width=2, font=("Consolas", 8),
                  bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                  command=lambda: self._change_tolerance(-8)).pack(side="left")
        tk.Label(self._tol_frame, textvariable=self._tol_var,
                 font=("Consolas", 9, "bold"), bg=BG_PANEL, fg=TEXT_PRIMARY,
                 width=3).pack(side="left")
        tk.Button(self._tol_frame, text="+", width=2, font=("Consolas", 8),
                  bg=BUTTON_BG, fg=TEXT_PRIMARY, relief="flat",
                  command=lambda: self._change_tolerance(8)).pack(side="left")

        # Bottom gradient border (cyan -> purple)
        self._border_canvas = tk.Canvas(self, height=2, bg=BG_PANEL,
                                        highlightthickness=0)
        self._border_canvas.pack(side="bottom", fill="x")
        self.bind("<Configure>", self._draw_gradient_border)

        self.set_tool("pen")

    def _draw_gradient_border(self, event=None):
        c = self._border_canvas
        c.delete("all")
        w = c.winfo_width()
        if w < 2:
            return
        from src.ui.theme import blend_color, ACCENT_PURPLE
        steps = min(w, 100)
        seg_w = w / steps
        for i in range(steps):
            color = blend_color(ACCENT_CYAN, ACCENT_PURPLE, i / max(1, steps - 1))
            x1 = int(i * seg_w)
            x2 = int((i + 1) * seg_w)
            c.create_rectangle(x1, 0, x2, 2, fill=color, outline="")

    def set_tool(self, tool_name: str):
        """Update the options bar for the given tool."""
        self.current_tool = tool_name
        self._tool_label.config(text=tool_name.capitalize())
        opts = TOOL_OPTIONS.get(tool_name, {})

        # Show/hide control frames
        for frame, key in [
            (self._size_frame, "size"),
            (self._sym_frame, "symmetry"),
            (self._dither_frame, "dither"),
            (self._pp_frame, "pixel_perfect"),
            (self._tol_frame, "tolerance"),
        ]:
            if opts.get(key):
                frame.pack(side="left", padx=2)
            else:
                frame.pack_forget()

    def get_size(self) -> int:
        return self._size_var.get()

    def set_size(self, size: int):
        self._size_var.set(max(1, min(15, size)))

    def get_symmetry(self) -> str:
        return self._sym_var.get()

    def set_symmetry(self, mode: str):
        self._sym_var.set(mode)

    def get_tolerance(self) -> int:
        return self._tol_var.get()

    def _change_size(self, delta):
        new = max(1, min(15, self._size_var.get() + delta))
        self._size_var.set(new)
        if self._on_size_change:
            self._on_size_change(new)

    def _cycle_symmetry(self):
        idx = self._sym_options.index(self._sym_var.get())
        new_mode = self._sym_options[(idx + 1) % len(self._sym_options)]
        self._sym_var.set(new_mode)
        if self._on_symmetry_change:
            self._on_symmetry_change(new_mode)

    def _cycle_dither(self):
        if self._on_dither_change:
            self._on_dither_change()

    def _toggle_pp(self):
        self._pp_var.set(not self._pp_var.get())
        self._pp_btn.config(text=f"PP: {'On' if self._pp_var.get() else 'Off'}")
        if self._on_pixel_perfect_toggle:
            self._on_pixel_perfect_toggle()

    def _change_tolerance(self, delta):
        new = max(0, min(255, self._tol_var.get() + delta))
        self._tol_var.set(new)
        if self._on_tolerance_change:
            self._on_tolerance_change(new)

    def update_dither_label(self, name: str):
        self._dither_var.set(name)

    def update_symmetry_label(self, mode: str):
        self._sym_var.set(mode)

    def update_pixel_perfect_label(self, on: bool):
        self._pp_var.set(on)
        self._pp_btn.config(text=f"PP: {'On' if on else 'Off'}")
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_options_bar.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/ui/options_bar.py tests/test_options_bar.py
git commit -m "feat(options-bar): context-sensitive tool options bar"
```

---

### Task 7: Create Timeline Panel — Data Layer

**Files:**
- Create: `src/ui/timeline.py`
- Test: `tests/test_timeline.py` (create)

This is the biggest task. We split it into two sub-tasks: data/logic layer (Task 7) and visual rendering (Task 8).

**Step 1: Write the failing test**

```python
# tests/test_timeline.py
import pytest
import tkinter as tk
from src.animation import AnimationTimeline


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
    from src.layer import Layer
    from src.pixel_data import PixelGrid
    layer = Layer("Test", PixelGrid(16, 16))
    assert layer.locked == False
    layer.locked = True
    assert layer.locked == True
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_timeline.py -v`
Expected: FAIL (or partial pass depending on Task 3 completion)

**Step 3: Ensure layer.locked is wired** (verify `src/layer.py:17` has `self.locked = False`)

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_timeline.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add tests/test_timeline.py
git commit -m "test(timeline): add data layer tests for per-frame duration and layer lock"
```

---

### Task 8: Create Timeline Panel — UI Widget

**Files:**
- Create: `src/ui/timeline.py`
- Test: Manual visual testing (Tkinter widget)

**Step 1: Implement the TimelinePanel widget**

This is a large visual component. Create `src/ui/timeline.py`:

```python
# src/ui/timeline.py
"""Bottom Layer x Frame grid timeline panel for RetroSprite."""

import tkinter as tk
from src.ui.theme import (
    BG_DEEP, BG_PANEL, BG_PANEL_ALT, BORDER, ACCENT_CYAN, ACCENT_MAGENTA,
    ACCENT_PURPLE, SUCCESS, WARNING, TEXT_PRIMARY, TEXT_SECONDARY,
    BUTTON_BG, BUTTON_HOVER, blend_color, hex_to_rgb, rgb_to_hex
)


class TimelinePanel(tk.Frame):
    """Combined layer+frame grid timeline, docked at the bottom of the window."""

    def __init__(self, parent, timeline=None,
                 on_frame_select=None, on_layer_select=None,
                 on_layer_visibility=None, on_layer_lock=None,
                 on_layer_add=None, on_layer_delete=None,
                 on_layer_rename=None, on_layer_duplicate=None,
                 on_layer_merge=None, on_layer_opacity=None,
                 on_frame_add=None, on_frame_delete=None,
                 on_frame_duplicate=None, on_frame_duration_change=None,
                 on_play=None, on_stop=None,
                 on_onion_toggle=None, on_onion_range_change=None,
                 on_playback_mode=None):
        super().__init__(parent, bg=BG_DEEP)

        self._timeline = timeline
        self._callbacks = {
            "frame_select": on_frame_select,
            "layer_select": on_layer_select,
            "layer_visibility": on_layer_visibility,
            "layer_lock": on_layer_lock,
            "layer_add": on_layer_add,
            "layer_delete": on_layer_delete,
            "layer_rename": on_layer_rename,
            "layer_duplicate": on_layer_duplicate,
            "layer_merge": on_layer_merge,
            "layer_opacity": on_layer_opacity,
            "frame_add": on_frame_add,
            "frame_delete": on_frame_delete,
            "frame_duplicate": on_frame_duplicate,
            "frame_duration_change": on_frame_duration_change,
            "play": on_play,
            "stop": on_stop,
            "onion_toggle": on_onion_toggle,
            "onion_range_change": on_onion_range_change,
            "playback_mode": on_playback_mode,
        }

        self._cel_size = 48  # Size of each cel in the grid
        self._layer_header_width = 140  # Width of layer name column
        self._playing = False
        self._onion_on = False
        self._onion_range = 1
        self._playback_mode = "forward"

        self._build_ui()

    def _build_ui(self):
        # --- Drag handle at the top ---
        self._handle = tk.Frame(self, height=5, bg=BORDER, cursor="sb_v_double_arrow")
        self._handle.pack(fill="x", side="top")
        self._handle.bind("<ButtonPress-1>", self._on_drag_start)
        self._handle.bind("<B1-Motion>", self._on_drag_motion)

        # --- Main content area ---
        content = tk.Frame(self, bg=BG_DEEP)
        content.pack(fill="both", expand=True, side="top")

        # --- Tag strip + frame headers + cel grid (scrollable) ---
        grid_area = tk.Frame(content, bg=BG_DEEP)
        grid_area.pack(fill="both", expand=True, side="top")

        # Layer sidebar (left, fixed width)
        self._layer_sidebar = tk.Frame(grid_area, width=self._layer_header_width, bg=BG_PANEL)
        self._layer_sidebar.pack(side="left", fill="y")
        self._layer_sidebar.pack_propagate(False)

        # Scrollable grid area (right)
        self._grid_scroll_frame = tk.Frame(grid_area, bg=BG_DEEP)
        self._grid_scroll_frame.pack(side="left", fill="both", expand=True)

        self._h_scrollbar = tk.Scrollbar(self._grid_scroll_frame, orient="horizontal",
                                         bg=BG_DEEP, troughcolor=BG_PANEL)
        self._h_scrollbar.pack(side="bottom", fill="x")

        self._grid_canvas = tk.Canvas(self._grid_scroll_frame, bg=BG_DEEP,
                                      highlightthickness=0,
                                      xscrollcommand=self._h_scrollbar.set)
        self._grid_canvas.pack(fill="both", expand=True)
        self._h_scrollbar.config(command=self._grid_canvas.xview)

        self._grid_inner = tk.Frame(self._grid_canvas, bg=BG_DEEP)
        self._grid_canvas.create_window((0, 0), window=self._grid_inner, anchor="nw")
        self._grid_inner.bind("<Configure>",
                              lambda e: self._grid_canvas.configure(
                                  scrollregion=self._grid_canvas.bbox("all")))

        # --- Transport bar (bottom) ---
        self._transport = tk.Frame(self, bg=BG_PANEL, height=32)
        self._transport.pack(fill="x", side="bottom")
        self._transport.pack_propagate(False)
        self._build_transport()

    def _build_transport(self):
        f = self._transport

        # Play controls
        btn_cfg = dict(font=("Consolas", 9), bg=BUTTON_BG, fg=TEXT_PRIMARY,
                       relief="flat", width=3, activebackground=BUTTON_HOVER,
                       activeforeground=ACCENT_CYAN)

        tk.Button(f, text="<<", command=self._step_back, **btn_cfg).pack(side="left", padx=2)
        tk.Button(f, text=">>", command=self._step_forward, **btn_cfg).pack(side="left", padx=2)

        self._play_btn = tk.Button(f, text="\u25B6", command=self._on_play, **btn_cfg)
        self._play_btn.pack(side="left", padx=2)

        self._stop_btn = tk.Button(f, text="\u25A0", command=self._on_stop, **btn_cfg)
        self._stop_btn.pack(side="left", padx=2)

        # Separator
        tk.Frame(f, width=1, bg=ACCENT_CYAN).pack(side="left", fill="y", padx=8, pady=4)

        # Playback mode
        self._mode_var = tk.StringVar(value="fwd")
        self._mode_btn = tk.Button(f, textvariable=self._mode_var, width=4,
                                   command=self._cycle_playback_mode, **btn_cfg)
        self._mode_btn.pack(side="left", padx=2)

        # Separator
        tk.Frame(f, width=1, bg=ACCENT_CYAN).pack(side="left", fill="y", padx=8, pady=4)

        # Onion skin
        self._onion_btn = tk.Button(f, text="Onion: Off", width=9,
                                    command=self._toggle_onion, **btn_cfg)
        self._onion_btn.pack(side="left", padx=2)

        tk.Label(f, text="Range:", font=("Consolas", 8), bg=BG_PANEL,
                 fg=TEXT_SECONDARY).pack(side="left", padx=(4, 0))
        self._onion_range_var = tk.IntVar(value=1)
        self._onion_spin = tk.Spinbox(f, from_=1, to=5, width=2,
                                      textvariable=self._onion_range_var,
                                      font=("Consolas", 8), bg=BG_PANEL_ALT,
                                      fg=TEXT_PRIMARY, buttonbackground=BUTTON_BG,
                                      command=self._on_onion_range)
        self._onion_spin.pack(side="left", padx=2)

        # Separator
        tk.Frame(f, width=1, bg=ACCENT_CYAN).pack(side="left", fill="y", padx=8, pady=4)

        # Add Frame / Add Layer buttons (right side)
        tk.Button(f, text="+ Layer", command=self._on_add_layer,
                  font=("Consolas", 8), bg=BUTTON_BG, fg=ACCENT_PURPLE,
                  relief="flat", activebackground=BUTTON_HOVER).pack(side="right", padx=4)
        tk.Button(f, text="+ Frame", command=self._on_add_frame,
                  font=("Consolas", 8), bg=BUTTON_BG, fg=ACCENT_CYAN,
                  relief="flat", activebackground=BUTTON_HOVER).pack(side="right", padx=4)

    def refresh(self):
        """Rebuild the entire grid from the current timeline state."""
        if not self._timeline:
            return

        # Clear existing
        for w in self._layer_sidebar.winfo_children():
            w.destroy()
        for w in self._grid_inner.winfo_children():
            w.destroy()

        frames = self._timeline._frames
        if not frames:
            return

        current_frame_idx = self._timeline._current_index
        current_frame = frames[current_frame_idx]
        num_frames = len(frames)
        num_layers = len(current_frame.layers)
        active_layer = current_frame.active_layer_index

        # --- Tag strip row in grid_inner ---
        tag_frame = tk.Frame(self._grid_inner, bg=BG_DEEP, height=16)
        tag_frame.grid(row=0, column=0, columnspan=num_frames, sticky="ew")
        self._draw_tags(tag_frame, num_frames)

        # --- Frame header row ---
        for fi in range(num_frames):
            f = frames[fi]
            is_current = (fi == current_frame_idx)
            bg = ACCENT_CYAN if is_current else BG_PANEL
            fg = BG_DEEP if is_current else TEXT_SECONDARY

            header = tk.Frame(self._grid_inner, width=self._cel_size, height=20, bg=bg)
            header.grid(row=1, column=fi, padx=1, pady=(0, 1), sticky="ew")
            header.grid_propagate(False)

            lbl = tk.Label(header, text=f"{fi+1}", font=("Consolas", 7, "bold"),
                           bg=bg, fg=fg)
            lbl.pack(side="top")

            dur_lbl = tk.Label(header, text=f"{f.duration_ms}ms",
                               font=("Consolas", 6), bg=bg, fg=fg)
            dur_lbl.pack(side="top")
            dur_lbl.bind("<Double-Button-1>",
                         lambda e, idx=fi: self._edit_frame_duration(idx))

        # --- Layer sidebar labels ---
        # Spacer for tag + header rows
        spacer = tk.Frame(self._layer_sidebar, height=36, bg=BG_PANEL)
        spacer.pack(fill="x")

        for li in range(num_layers - 1, -1, -1):  # Top layer first
            layer = current_frame.layers[li]
            is_active = (li == active_layer)

            row = tk.Frame(self._layer_sidebar, height=self._cel_size, bg=BG_PANEL)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)

            # Visibility toggle
            vis_text = "\u25C9" if layer.visible else "\u25CB"  # ◉ or ○
            vis_btn = tk.Button(row, text=vis_text, width=2,
                                font=("Consolas", 8), bg=BG_PANEL, fg=ACCENT_CYAN,
                                relief="flat", command=lambda idx=li: self._toggle_visibility(idx))
            vis_btn.pack(side="left", padx=1)

            # Lock toggle
            lock_text = "\u26BF" if layer.locked else "\u26AC"  # ⚿ or ⚬
            lock_color = WARNING if layer.locked else TEXT_SECONDARY
            lock_btn = tk.Button(row, text=lock_text, width=2,
                                 font=("Consolas", 8), bg=BG_PANEL, fg=lock_color,
                                 relief="flat", command=lambda idx=li: self._toggle_lock(idx))
            lock_btn.pack(side="left", padx=1)

            # Layer name
            name_fg = ACCENT_CYAN if is_active else TEXT_PRIMARY
            name_bg = BG_PANEL_ALT if is_active else BG_PANEL
            name_lbl = tk.Label(row, text=layer.name, font=("Consolas", 8),
                                bg=name_bg, fg=name_fg, anchor="w")
            name_lbl.pack(side="left", fill="x", expand=True, padx=2)
            name_lbl.bind("<Button-1>", lambda e, idx=li: self._select_layer(idx))
            name_lbl.bind("<Double-Button-1>", lambda e, idx=li: self._rename_layer(idx))

        # --- Cel grid ---
        for li in range(num_layers - 1, -1, -1):
            grid_row = (num_layers - 1 - li) + 2  # +2 for tag + header rows
            for fi in range(num_frames):
                frame = frames[fi]
                is_current_frame = (fi == current_frame_idx)
                is_active_layer = (li == active_layer)

                # Determine cel state
                has_content = False
                if li < len(frame.layers):
                    layer = frame.layers[li]
                    has_content = layer.pixels.data.any()  # Has any non-zero pixels

                if is_current_frame and is_active_layer:
                    bg = ACCENT_CYAN
                    fg = BG_DEEP
                elif is_current_frame:
                    bg = blend_color(BG_PANEL_ALT, ACCENT_CYAN, 0.15)
                    fg = ACCENT_CYAN
                elif is_active_layer:
                    bg = BG_PANEL_ALT
                    fg = ACCENT_CYAN
                else:
                    bg = BG_PANEL if has_content else BG_DEEP
                    fg = TEXT_SECONDARY

                cel = tk.Frame(self._grid_inner, width=self._cel_size,
                               height=self._cel_size, bg=bg)
                cel.grid(row=grid_row, column=fi, padx=1, pady=1, sticky="nsew")
                cel.grid_propagate(False)

                # Content indicator
                if has_content:
                    dot = tk.Label(cel, text="\u25A0", font=("Consolas", 10),
                                   bg=bg, fg=fg)
                    dot.pack(expand=True)
                    dot.bind("<Button-1>",
                             lambda e, f=fi, l=li: self._select_cel(f, l))
                else:
                    cel.bind("<Button-1>",
                             lambda e, f=fi, l=li: self._select_cel(f, l))

    def _draw_tags(self, container, num_frames):
        """Draw colored tag bars above frame columns."""
        if not self._timeline or not self._timeline.tags:
            return
        for tag in self._timeline.tags:
            # Pick a neon color
            colors = [ACCENT_CYAN, ACCENT_MAGENTA, ACCENT_PURPLE, SUCCESS, WARNING]
            color = tag.get("color", colors[0])
            if color.startswith("#") and len(color) >= 7:
                pass  # Use as-is
            else:
                color = ACCENT_CYAN

            start = tag.get("start", 0)
            end = tag.get("end", 0)
            name = tag.get("name", "")

            tag_lbl = tk.Label(container, text=name, font=("Consolas", 6),
                               bg=color, fg=BG_DEEP, anchor="center")
            # Position using place for pixel-level control
            x_start = start * (self._cel_size + 2)
            width = (end - start + 1) * (self._cel_size + 2)
            tag_lbl.place(x=x_start, y=0, width=width, height=14)

    def _select_cel(self, frame_idx, layer_idx):
        if self._callbacks["frame_select"]:
            self._callbacks["frame_select"](frame_idx)
        if self._callbacks["layer_select"]:
            self._callbacks["layer_select"](layer_idx)
        self.refresh()

    def _select_layer(self, layer_idx):
        if self._callbacks["layer_select"]:
            self._callbacks["layer_select"](layer_idx)
        self.refresh()

    def _toggle_visibility(self, layer_idx):
        if self._callbacks["layer_visibility"]:
            self._callbacks["layer_visibility"](layer_idx)
        self.refresh()

    def _toggle_lock(self, layer_idx):
        if self._callbacks["layer_lock"]:
            self._callbacks["layer_lock"](layer_idx)
        self.refresh()

    def _rename_layer(self, layer_idx):
        if self._callbacks["layer_rename"]:
            self._callbacks["layer_rename"](layer_idx)

    def _edit_frame_duration(self, frame_idx):
        """Open inline edit for frame duration."""
        if not self._timeline:
            return
        from tkinter import simpledialog
        frame = self._timeline._frames[frame_idx]
        new_ms = simpledialog.askinteger(
            "Frame Duration", f"Duration for frame {frame_idx + 1} (ms):",
            initialvalue=frame.duration_ms, minvalue=10, maxvalue=5000
        )
        if new_ms is not None:
            frame.duration_ms = new_ms
            if self._callbacks["frame_duration_change"]:
                self._callbacks["frame_duration_change"](frame_idx, new_ms)
            self.refresh()

    def _on_play(self):
        self._playing = True
        self._play_btn.config(fg=ACCENT_CYAN)
        if self._callbacks["play"]:
            self._callbacks["play"]()

    def _on_stop(self):
        self._playing = False
        self._play_btn.config(fg=TEXT_PRIMARY)
        if self._callbacks["stop"]:
            self._callbacks["stop"]()

    def _step_forward(self):
        if self._timeline:
            idx = self._timeline._current_index
            num = len(self._timeline._frames)
            self._select_cel((idx + 1) % num,
                             self._timeline._frames[idx].active_layer_index)

    def _step_back(self):
        if self._timeline:
            idx = self._timeline._current_index
            num = len(self._timeline._frames)
            self._select_cel((idx - 1) % num,
                             self._timeline._frames[idx].active_layer_index)

    def _cycle_playback_mode(self):
        modes = [("fwd", "forward"), ("rev", "reverse"), ("pp", "pingpong")]
        current_labels = [m[0] for m in modes]
        idx = 0
        for i, (label, _) in enumerate(modes):
            if self._mode_var.get() == label:
                idx = i
                break
        next_idx = (idx + 1) % len(modes)
        self._mode_var.set(modes[next_idx][0])
        self._playback_mode = modes[next_idx][1]
        if self._callbacks["playback_mode"]:
            self._callbacks["playback_mode"](self._playback_mode)

    def _toggle_onion(self):
        self._onion_on = not self._onion_on
        self._onion_btn.config(
            text=f"Onion: {'On' if self._onion_on else 'Off'}",
            fg=ACCENT_CYAN if self._onion_on else TEXT_PRIMARY
        )
        if self._callbacks["onion_toggle"]:
            self._callbacks["onion_toggle"](self._onion_on)

    def _on_onion_range(self):
        self._onion_range = self._onion_range_var.get()
        if self._callbacks["onion_range_change"]:
            self._callbacks["onion_range_change"](self._onion_range)

    def _on_add_frame(self):
        if self._callbacks["frame_add"]:
            self._callbacks["frame_add"]()
        self.refresh()

    def _on_add_layer(self):
        if self._callbacks["layer_add"]:
            self._callbacks["layer_add"]()
        self.refresh()

    # --- Drag resize ---
    def _on_drag_start(self, event):
        self._drag_start_y = event.y_root
        self._drag_start_height = self.winfo_height()

    def _on_drag_motion(self, event):
        delta = self._drag_start_y - event.y_root
        new_height = max(100, min(400, self._drag_start_height + delta))
        self.config(height=new_height)

    def set_timeline(self, timeline):
        self._timeline = timeline
        self.refresh()
```

**Step 2: Verify it loads without errors**

Run: `python -c "from src.ui.timeline import TimelinePanel; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add src/ui/timeline.py
git commit -m "feat(timeline): add bottom Layer x Frame grid timeline panel"
```

---

## Phase 3: Rewrites (Toolbar + Right Panel)

### Task 9: Rewrite Toolbar as Icon-Only Strip

**Files:**
- Modify: `src/ui/toolbar.py:1-257` (full rewrite)
- Test: `tests/test_toolbar.py` (create)

**Step 1: Write the failing test**

```python
# tests/test_toolbar.py
import pytest
import tkinter as tk
from src.ui.toolbar import Toolbar


@pytest.fixture
def root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def test_toolbar_creation(root):
    selected = []
    toolbar = Toolbar(root, on_tool_change=lambda t: selected.append(t))
    assert toolbar is not None
    assert toolbar.winfo_exists()


def test_toolbar_has_all_tools(root):
    toolbar = Toolbar(root, on_tool_change=lambda t: None)
    expected_tools = ["pen", "eraser", "blur", "fill", "ellipse",
                      "pick", "select", "wand", "line", "rect", "hand"]
    assert set(toolbar.tool_names) == set(expected_tools)


def test_toolbar_select_tool(root):
    selected = []
    toolbar = Toolbar(root, on_tool_change=lambda t: selected.append(t))
    toolbar.select_tool("eraser")
    assert toolbar.active_tool == "eraser"


def test_toolbar_width_is_narrow(root):
    toolbar = Toolbar(root, on_tool_change=lambda t: None)
    toolbar.update_idletasks()
    # Should be narrow (~48px) since we removed all text controls
    assert toolbar.winfo_reqwidth() <= 80
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_toolbar.py -v`
Expected: FAIL — old toolbar has different API

**Step 3: Rewrite toolbar**

Replace entire content of `src/ui/toolbar.py` with an icon-only vertical strip. Key changes:
- Remove brush size, symmetry, dither, pixel perfect, wand tolerance sections (moved to options bar)
- Each tool button is a 32x32 icon from IconPipeline
- Active tool gets glow variant
- Tooltip on hover
- Width ~48px
- `tool_names` property listing all available tools
- `active_tool` property
- `select_tool(name)` method

Full implementation: the `__init__` creates the scrollable frame, iterates `TOOL_ICON_MAP` keys, creates a button per tool using `IconPipeline.get_icon()`, stores `PhotoImage` references. `select_tool` updates the active button's image to the glow variant and resets the previous active button.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_toolbar.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/ui/toolbar.py tests/test_toolbar.py
git commit -m "feat(toolbar): rewrite as icon-only vertical strip with glow effects"
```

---

### Task 10: Rewrite Right Panel (Collapsible, No Layers/Frames)

**Files:**
- Modify: `src/ui/right_panel.py:1-481` (full rewrite)
- Test: `tests/test_right_panel.py` (create)

**Step 1: Write the failing test**

```python
# tests/test_right_panel.py
import pytest
import tkinter as tk
from src.ui.right_panel import RightPanel, CollapsibleSection


@pytest.fixture
def root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def test_collapsible_section(root):
    section = CollapsibleSection(root, title="Test")
    section.pack()
    assert section.is_expanded == True
    section.toggle()
    assert section.is_expanded == False
    section.toggle()
    assert section.is_expanded == True


def test_right_panel_has_no_layer_panel(root):
    panel = RightPanel(root)
    assert not hasattr(panel, "layer_panel")


def test_right_panel_has_no_frame_panel(root):
    panel = RightPanel(root)
    assert not hasattr(panel, "frame_panel")


def test_right_panel_has_palette(root):
    panel = RightPanel(root)
    assert hasattr(panel, "palette_section")


def test_right_panel_has_color_picker(root):
    panel = RightPanel(root)
    assert hasattr(panel, "picker_section")
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_right_panel.py -v`
Expected: FAIL — old right panel has layer_panel and frame_panel

**Step 3: Rewrite right panel**

Key changes:
- Remove `LayerPanel` and `FramePanel` classes entirely
- Add `CollapsibleSection` widget class (header bar + expand/collapse + content frame)
- Each section has a left-edge gradient accent line (2px, cyan→purple)
- Fix `PalettePanel`: add recent colors row (last 10), stop full-rebuild on every refresh
- Fix `ColorPickerPanel`: don't fire `_on_picker_color` on drag (only on click release), add alpha slider
- Fix `AnimationPreview`: dynamic sizing based on panel width
- `CompressionPanel`: themed consistently

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_right_panel.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/ui/right_panel.py tests/test_right_panel.py
git commit -m "feat(right-panel): rewrite with collapsible sections, remove layers/frames"
```

---

## Phase 4: Integration (App Assembly + Dialog Redesign)

### Task 11: Rewire App Layout

**Files:**
- Modify: `src/app.py` (major changes across multiple sections)

This is the integration task — wiring the new components together.

**Step 1: Update imports** (top of `src/app.py`)

Add:
```python
from src.ui.timeline import TimelinePanel
from src.ui.options_bar import OptionsBar
```

**Step 2: Rewrite `_build_ui` method** (line 245+)

New layout order:
1. Menu bar (unchanged)
2. Options bar — `pack(side="top", fill="x")` on root
3. Main frame — `pack(fill="both", expand=True)`
   - Toolbar (left, `fill="y"`)
   - Right panel (right, `fill="y"`)
   - Canvas (center, `fill="both", expand=True`)
4. Timeline panel — `pack(side="bottom", fill="x")` on root, with initial height ~180px
5. Status bar — `pack(side="bottom", fill="x")` on root

**Step 3: Remove old callback monkey-patching** (lines 256-259)

Wire symmetry/dither/pixel-perfect/tolerance through `OptionsBar` callbacks instead.

**Step 4: Remove LayerPanel/FramePanel destroy-rebuild** (lines 272-298)

Wire layer/frame operations through `TimelinePanel` callbacks.

**Step 5: Remove onion skin checkbutton** (lines 301-310)

Onion skin now controlled from timeline transport bar.

**Step 6: Update `_animate_step`** (lines 1070-1106)

- Read `duration_ms` from `current_frame_obj().duration_ms` instead of the old spinbox
- Remove the call to `_resize_canvas()` inside `_refresh_canvas` during playback
- Update timeline panel playhead on each frame change

**Step 7: Add layer lock check in drawing tools**

In `_on_pixel_click` and `_on_pixel_drag`, check `current_layer.locked` before applying any drawing operation. If locked, show a brief status message "Layer is locked" and return.

**Step 8: Wire OptionsBar tool change**

When a tool is selected (via toolbar click or keyboard shortcut), call `self.options_bar.set_tool(tool_name)` to update the context-sensitive controls.

When size changes in options bar, update `self.brush_size`.
When symmetry changes, update `self._symmetry_mode`.
Etc.

**Step 9: Wire TimelinePanel callbacks**

Map each timeline callback to the appropriate existing method in app.py:
- `on_frame_select` → `_select_frame(idx)`
- `on_layer_select` → `_select_layer(idx)`
- `on_layer_visibility` → `_toggle_layer_visibility(idx)`
- `on_layer_lock` → new method that toggles `layer.locked`
- `on_layer_add` → `_add_layer()`
- `on_frame_add` → `_add_frame()`
- `on_play` → `_play_animation()`
- `on_stop` → `_stop_animation()`
- etc.

**Step 10: Update `_refresh_canvas` to pass onion grids**

Instead of passing a single `onion_grid`, collect past/future frames based on the timeline's onion range setting and pass `onion_past_grids` and `onion_future_grids` to `build_render_image`.

**Step 11: Verify the app launches**

Run: `python main.py`
Expected: App launches with new layout (toolbar icons, options bar, bottom timeline, right panel without layers/frames)

**Step 12: Run all tests**

Run: `python -m pytest -v`
Expected: All tests pass

**Step 13: Commit**

```bash
git add src/app.py
git commit -m "feat(app): rewire layout with timeline, options bar, and icon toolbar"
```

---

### Task 12: Redesign Dialogs with Cyberpunk Theme

**Files:**
- Modify: `src/ui/dialogs.py:1-181`

**Step 1: Update `ask_startup` dialog** (line 57-142)

- Add neon glow effect to "RetroSprite" title text (using a canvas with glow behind text)
- Use gradient border separators
- Size buttons get neon hover effects (change border color to ACCENT_CYAN on enter, revert on leave)
- "Open .retro Project" button uses ACCENT_MAGENTA with glow

**Step 2: Replace `simpledialog` calls with themed dialogs**

Create a `NeonDialog` base class:
```python
class NeonDialog(tk.Toplevel):
    """Base class for cyberpunk-themed dialogs."""
    def __init__(self, parent, title="", width=300, height=200):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=BG_DEEP)
        self.geometry(f"{width}x{height}")
        self.transient(parent)
        self.grab_set()
        self.result = None
        # Add gradient top border
        ...
```

Use this for tag creation, frame duration edit, layer rename, etc.

**Step 3: Verify dialogs render correctly**

Manual test: launch app, click File > New, verify startup dialog has neon effects.

**Step 4: Commit**

```bash
git add src/ui/dialogs.py
git commit -m "feat(dialogs): cyberpunk neon-themed dialogs with glow effects"
```

---

### Task 13: Add Status Bar Scanline Effect

**Files:**
- Modify: `src/app.py` (status bar section, lines 349-353)

**Step 1: Replace the plain `tk.Label` status bar with a `tk.Canvas`-based status bar**

```python
# In _build_ui, replace the status label with:
self._status_canvas = tk.Canvas(self.root, height=22, bg=BG_PANEL, highlightthickness=0)
self._status_canvas.pack(side="bottom", fill="x")
# Draw scanline texture overlay
self._status_canvas.bind("<Configure>", self._draw_status_scanlines)
```

The status text is drawn on top of the scanline texture using `create_text`.

**Step 2: Implement `_draw_status_scanlines`**

Uses `create_scanline_texture` from `src/ui/effects.py` to generate the CRT effect, converts to `PhotoImage`, and places it as the background of the status canvas.

**Step 3: Verify visually**

Run: `python main.py`
Expected: Status bar has subtle CRT scanline texture

**Step 4: Commit**

```bash
git add src/app.py
git commit -m "feat(status-bar): add CRT scanline texture effect"
```

---

## Phase 5: Polish & Bug Fixes

### Task 14: Fix Color Picker Drag Flooding

**Files:**
- Modify: `src/ui/right_panel.py` (ColorPickerPanel)

**Step 1: Change `_on_pick` to only call the callback on mouse release, not on drag**

Bind `<ButtonRelease-1>` for the final color selection instead of `<B1-Motion>`. During drag, only update the preview swatch — don't fire the callback.

**Step 2: Verify**

Manual test: drag across color picker, palette should NOT grow. Click to select a color, then click "+ Palette" to add it.

**Step 3: Commit**

```bash
git add src/ui/right_panel.py
git commit -m "fix(color-picker): stop flooding palette on drag, only add on explicit click"
```

---

### Task 15: Download and Add Phosphor Icons

**Files:**
- Create: `icons/*.png` (11 icon files)

**Step 1: Download Phosphor icon PNGs**

Visit https://phosphoricons.com/ and download the "bold" variant PNGs for:
- pen.png, eraser.png, drop.png (for blur), paint-bucket.png, circle.png,
  eyedropper.png, selection.png, magic-wand.png, line-segment.png,
  rectangle.png, hand.png

Place them in the `icons/` directory.

**Step 2: Verify icon pipeline processes them**

Run: `python -c "from src.ui.icons import IconPipeline; p = IconPipeline(); print(p.get_icon('pen'))"`
Expected: Returns a tuple of (normal_img, glow_img) PIL Images

**Step 3: Commit**

```bash
git add icons/
git commit -m "assets: add Phosphor icon PNGs for toolbar"
```

---

### Task 16: Run Full Test Suite & Fix Breakages

**Files:**
- Various test files

**Step 1: Run all tests**

Run: `python -m pytest -v`

**Step 2: Fix any failing tests**

Common expected breakages:
- Tests that imported `LayerPanel` or `FramePanel` from `right_panel.py`
- Tests that relied on toolbar having size/symmetry controls
- Tests that used old `build_render_image` signature without new params

Fix each failure, ensuring backward compatibility where needed.

**Step 3: Verify all pass**

Run: `python -m pytest -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add -A
git commit -m "fix: resolve test breakages from UI overhaul"
```

---

### Task 17: Visual Polish Pass

**Files:**
- Various UI files

**Step 1: Launch app and check each component visually**

Checklist:
- [ ] Toolbar shows pixelated icons, active tool has glow
- [ ] Options bar shows/hides controls per tool
- [ ] Timeline grid displays layers x frames correctly
- [ ] Tag bars render with neon colors
- [ ] Frame duration double-click edit works
- [ ] Layer lock/visibility toggles work
- [ ] Playhead highlights current frame column
- [ ] Transport controls play/stop/step work
- [ ] Right panel sections collapse/expand
- [ ] Color picker doesn't flood palette
- [ ] Preview scales dynamically
- [ ] Panel border gradients render (cyan to purple)
- [ ] Status bar has scanline texture
- [ ] Startup dialog has neon glow title
- [ ] Onion skin shows multi-frame with color tinting

**Step 2: Fix any visual issues found**

**Step 3: Commit**

```bash
git add -A
git commit -m "polish: visual adjustments from UI overhaul review"
```

---

## Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| 1: Foundation | 1-5 | Theme, effects, model updates, icon pipeline |
| 2: New Components | 6-8 | Options bar, timeline panel |
| 3: Rewrites | 9-10 | Toolbar (icon-only), right panel (collapsible) |
| 4: Integration | 11-13 | App assembly, dialog redesign, status bar |
| 5: Polish | 14-17 | Bug fixes, icons, test fixes, visual polish |

**Total: 17 tasks across 5 phases**

**Critical path:** Tasks 1-2 (foundation) → Task 5 (icons) → Task 9 (toolbar rewrite) → Task 11 (app assembly). The timeline (Tasks 7-8) can be built in parallel with the icon pipeline.
