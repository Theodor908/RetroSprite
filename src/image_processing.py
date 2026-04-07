"""Image processing operations for pixel art."""
from __future__ import annotations
from PIL import Image, ImageFilter, ImageEnhance
from src.pixel_data import PixelGrid


def blur(grid: PixelGrid, radius: int = 1) -> PixelGrid:
    img = grid.to_pil_image()
    blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
    return PixelGrid.from_pil_image(blurred)


def scale(grid: PixelGrid, factor: float) -> PixelGrid:
    img = grid.to_pil_image()
    new_w = max(1, int(grid.width * factor))
    new_h = max(1, int(grid.height * factor))
    scaled = img.resize((new_w, new_h), Image.NEAREST)
    return PixelGrid.from_pil_image(scaled)


def rotate(grid: PixelGrid, degrees: int, algorithm: str = "rotsprite",
           pivot: tuple[int, int] | None = None) -> PixelGrid:
    """Rotate pixel grid using specified algorithm.

    Args:
        algorithm: "rotsprite" for pixel-art-aware, "fast" for nearest-neighbor
        pivot: rotation center (x, y). Defaults to image center.
    """
    from src.rotsprite import rotsprite_rotate, fast_rotate
    pixels = grid._pixels
    if algorithm == "rotsprite":
        rotated = rotsprite_rotate(pixels, degrees, pivot=pivot)
    else:
        rotated = fast_rotate(pixels, degrees, pivot=pivot)
    result = PixelGrid(grid.width, grid.height)
    result._pixels = rotated
    return result


def crop(grid: PixelGrid, x: int, y: int, w: int, h: int) -> PixelGrid:
    img = grid.to_pil_image()
    cropped = img.crop((x, y, x + w, y + h))
    return PixelGrid.from_pil_image(cropped)


def flip_horizontal(grid: PixelGrid) -> PixelGrid:
    img = grid.to_pil_image()
    flipped = img.transpose(Image.FLIP_LEFT_RIGHT)
    return PixelGrid.from_pil_image(flipped)


def flip_vertical(grid: PixelGrid) -> PixelGrid:
    img = grid.to_pil_image()
    flipped = img.transpose(Image.FLIP_TOP_BOTTOM)
    return PixelGrid.from_pil_image(flipped)


def adjust_brightness(grid: PixelGrid, factor: float) -> PixelGrid:
    img = grid.to_pil_image()
    enhancer = ImageEnhance.Brightness(img)
    enhanced = enhancer.enhance(factor)
    return PixelGrid.from_pil_image(enhanced)


def adjust_contrast(grid: PixelGrid, factor: float) -> PixelGrid:
    img = grid.to_pil_image()
    enhancer = ImageEnhance.Contrast(img)
    enhanced = enhancer.enhance(factor)
    return PixelGrid.from_pil_image(enhanced)


def _posterize_channel(value: int, levels: int) -> int:
    """Quantize a single channel value (0-255) to the given number of levels."""
    if levels <= 1:
        return 0
    step = 256 / levels
    quantized = int(value / step)
    return int(quantized * 255 / (levels - 1))


def posterize(grid: PixelGrid, levels: int = 4) -> PixelGrid:
    img = grid.to_pil_image()
    pixels = list(img.getdata())
    new_pixels = []
    for r, g, b, a in pixels:
        new_pixels.append((
            _posterize_channel(r, levels),
            _posterize_channel(g, levels),
            _posterize_channel(b, levels),
            a,
        ))
    result = Image.new("RGBA", img.size)
    result.putdata(new_pixels)
    return PixelGrid.from_pil_image(result)
