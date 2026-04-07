"""RotSprite pixel-art-aware rotation algorithm."""
from __future__ import annotations
import math
import numpy as np
from PIL import Image
from src.pixel_data import PixelGrid


def color_distance(a: tuple, b: tuple) -> int:
    """Manhattan distance in RGBA space between two color tuples."""
    return sum(abs(int(a[i]) - int(b[i])) for i in range(4))


def scale2x(pixels: np.ndarray, threshold: int = 48) -> np.ndarray:
    """Modified Scale2x with similarity threshold for RotSprite.

    Input: (H, W, 4) uint8 RGBA array.
    Output: (H*2, W*2, 4) uint8 RGBA array.
    """
    h, w = pixels.shape[:2]
    result = np.zeros((h * 2, w * 2, 4), dtype=np.uint8)

    # Pad pixels with edge values for border handling
    padded = np.pad(pixels, ((1, 1), (1, 1), (0, 0)), mode='edge')

    # Extract neighbors: B=top, D=left, E=center, F=right, H=bot
    B = padded[0:h, 1:w+1]    # top
    D = padded[1:h+1, 0:w]    # left
    E = padded[1:h+1, 1:w+1]  # center (= original pixels)
    F = padded[1:h+1, 2:w+2]  # right
    H = padded[2:h+2, 1:w+1]  # bottom

    # Compute similarity masks using Manhattan distance
    def similar(a, b):
        diff = np.sum(np.abs(a.astype(np.int16) - b.astype(np.int16)), axis=-1)
        return diff < threshold

    def not_similar(a, b):
        diff = np.sum(np.abs(a.astype(np.int16) - b.astype(np.int16)), axis=-1)
        return diff >= threshold

    # Scale2x rules
    cond0 = similar(D, B) & not_similar(D, H) & not_similar(B, F)
    cond1 = similar(B, F) & not_similar(B, D) & not_similar(F, H)
    cond2 = similar(D, H) & not_similar(D, B) & not_similar(H, F)
    cond3 = similar(H, F) & not_similar(H, D) & not_similar(F, B)

    # Expand condition masks for RGBA channels
    cond0 = cond0[:, :, np.newaxis]
    cond1 = cond1[:, :, np.newaxis]
    cond2 = cond2[:, :, np.newaxis]
    cond3 = cond3[:, :, np.newaxis]

    result[0::2, 0::2] = np.where(cond0, D, E)  # E0
    result[0::2, 1::2] = np.where(cond1, F, E)  # E1
    result[1::2, 0::2] = np.where(cond2, D, E)  # E2
    result[1::2, 1::2] = np.where(cond3, F, E)  # E3

    return result


def fast_rotate(pixels: np.ndarray, angle: float,
                pivot: tuple[int, int] | None = None) -> np.ndarray:
    """Nearest-neighbor rotation. Quick but produces jagged edges."""
    if angle % 360 == 0:
        return pixels.copy()
    img = Image.fromarray(pixels, "RGBA")
    if pivot is not None:
        px, py = pivot
        rad = math.radians(-angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        a = cos_a
        b = sin_a
        c = px - cos_a * px - sin_a * py
        d = -sin_a
        e = cos_a
        f_val = py + sin_a * px - cos_a * py
        rotated = img.transform(img.size, Image.AFFINE,
                                (a, b, c, d, e, f_val),
                                resample=Image.NEAREST)
    else:
        rotated = img.rotate(-angle, resample=Image.NEAREST, expand=False)
    return np.array(rotated, dtype=np.uint8)


def _mode_downsample(pixels: np.ndarray, factor: int) -> np.ndarray:
    """Downsample by taking the most common color in each block."""
    h, w = pixels.shape[:2]
    new_h, new_w = h // factor, w // factor
    result = np.zeros((new_h, new_w, 4), dtype=np.uint8)

    for y in range(new_h):
        for x in range(new_w):
            block = pixels[y*factor:(y+1)*factor, x*factor:(x+1)*factor]
            flat = block.reshape(-1, 4)
            opaque = flat[flat[:, 3] > 0]
            if len(opaque) == 0:
                continue
            packed = (opaque[:, 0].astype(np.uint32) << 24 |
                      opaque[:, 1].astype(np.uint32) << 16 |
                      opaque[:, 2].astype(np.uint32) << 8 |
                      opaque[:, 3].astype(np.uint32))
            values, counts = np.unique(packed, return_counts=True)
            mode_packed = values[np.argmax(counts)]
            result[y, x] = [
                (mode_packed >> 24) & 0xFF,
                (mode_packed >> 16) & 0xFF,
                (mode_packed >> 8) & 0xFF,
                mode_packed & 0xFF,
            ]
    return result


def rotsprite_rotate(pixels: np.ndarray, angle: float,
                     pivot: tuple[int, int] | None = None) -> np.ndarray:
    """RotSprite: upscale 8x with Scale2x, rotate, then mode-downsample.
    Slower than fast_rotate but preserves pixel art edges much better."""
    if angle % 360 == 0:
        return pixels.copy()

    # Step 1: Scale up 8x with modified Scale2x (3 passes)
    upscaled = pixels
    for _ in range(3):
        upscaled = scale2x(upscaled)

    # Step 2: Rotate at 8x resolution (nearest neighbor)
    pivot_8x = None
    if pivot is not None:
        pivot_8x = (pivot[0] * 8, pivot[1] * 8)
    rotated = fast_rotate(upscaled, angle, pivot=pivot_8x)

    # Step 3: Downsample back to original size
    result = _mode_downsample(rotated, 8)

    return result
