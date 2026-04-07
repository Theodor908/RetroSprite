"""Cyberpunk neon visual effects for RetroSprite UI."""

from PIL import Image, ImageFilter
from src.ui.theme import hex_to_rgb, rgb_to_hex


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
    """Convert an icon to neon-colored with transparent background.

    Any pixel with alpha > 32 gets colorized to line_color, preserving its alpha.
    This handles both dark-on-transparent and light-on-transparent icons.
    """
    result = Image.new("RGBA", img.size, (0, 0, 0, 0))
    pixels = img.load()
    result_pixels = result.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            px = pixels[x, y]
            if len(px) == 4:
                r, g, b, a = px
            else:
                r, g, b = px
                a = 255
            if a < 32:
                continue  # Transparent — skip
            # Colorize: use the original alpha for smooth edges
            result_pixels[x, y] = (*line_color, a)
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
        colors.append(rgb_to_hex(r, g, b))
    return colors
