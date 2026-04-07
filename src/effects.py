"""Non-destructive layer effects for RetroSprite."""
from __future__ import annotations
import numpy as np
from PIL import Image, ImageFilter
from src.layer import apply_blend_mode


class LayerEffect:
    """A non-destructive effect applied to a layer during compositing."""

    def __init__(self, type: str, enabled: bool, params: dict):
        self.type = type
        self.enabled = enabled
        self.params = params

    def to_dict(self) -> dict:
        return {"type": self.type, "enabled": self.enabled, "params": self.params}

    @classmethod
    def from_dict(cls, data: dict) -> LayerEffect:
        return cls(data["type"], data["enabled"], data["params"])


def _shift_array(arr: np.ndarray, dx: int, dy: int) -> np.ndarray:
    """Shift a 2D RGBA array by (dx, dy), filling exposed edges with zeros."""
    result = np.zeros_like(arr)
    h, w = arr.shape[:2]
    sx_start = max(0, -dx)
    sx_end = min(w, w - dx)
    sy_start = max(0, -dy)
    sy_end = min(h, h - dy)
    dx_start = max(0, dx)
    dx_end = min(w, w + dx)
    dy_start = max(0, dy)
    dy_end = min(h, h + dy)
    if sx_end > sx_start and sy_end > sy_start:
        result[dy_start:dy_end, dx_start:dx_end] = arr[sy_start:sy_end, sx_start:sx_end]
    return result


def _gaussian_blur_rgba(pixels: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return pixels.copy()
    img = Image.fromarray(pixels, "RGBA")
    blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
    return np.array(blurred, dtype=np.uint8)


def _alpha_composite(below: np.ndarray, above: np.ndarray) -> np.ndarray:
    below_img = Image.fromarray(below, "RGBA")
    above_img = Image.fromarray(above, "RGBA")
    return np.array(Image.alpha_composite(below_img, above_img), dtype=np.uint8)


# ---------- CORE EFFECTS ----------

def apply_outline(pixels: np.ndarray, color: tuple, thickness: int,
                  mode: str, connectivity: int,
                  original_alpha: np.ndarray | None = None) -> np.ndarray:
    result = pixels.copy()
    h, w = pixels.shape[:2]
    alpha = original_alpha if original_alpha is not None else pixels[:, :, 3]

    if connectivity == 8:
        struct_offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                         (0, 1), (1, -1), (1, 0), (1, 1)]
    else:
        struct_offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    for _ in range(thickness):
        current_alpha = result[:, :, 3]
        opaque = current_alpha > 0

        if mode in ("outer", "both"):
            dilated = np.zeros_like(opaque)
            for dy, dx in struct_offsets:
                shifted = np.roll(np.roll(opaque, dy, axis=0), dx, axis=1)
                if dy < 0:
                    shifted[-1:, :] = False
                elif dy > 0:
                    shifted[:1, :] = False
                if dx < 0:
                    shifted[:, -1:] = False
                elif dx > 0:
                    shifted[:, :1] = False
                dilated |= shifted
            outline_mask = dilated & ~opaque
            result[outline_mask] = list(color)

        if mode in ("inner", "both"):
            eroded = np.ones_like(opaque)
            for dy, dx in struct_offsets:
                shifted = np.roll(np.roll(opaque, dy, axis=0), dx, axis=1)
                if dy < 0:
                    shifted[-1:, :] = False
                elif dy > 0:
                    shifted[:1, :] = False
                if dx < 0:
                    shifted[:, -1:] = False
                elif dx > 0:
                    shifted[:, :1] = False
                eroded &= shifted
            inner_mask = opaque & ~eroded
            result[inner_mask] = list(color)

    return result


def apply_drop_shadow(pixels: np.ndarray, color: tuple, offset_x: int,
                      offset_y: int, blur: int, opacity: float,
                      original_alpha: np.ndarray | None = None) -> np.ndarray:
    h, w = pixels.shape[:2]
    shadow = np.zeros((h, w, 4), dtype=np.uint8)
    alpha = original_alpha if original_alpha is not None else pixels[:, :, 3]
    shadow_mask = alpha > 0
    shadow_color = list(color[:3]) + [int(255 * opacity)]
    shadow[shadow_mask] = shadow_color
    shadow = _shift_array(shadow, offset_x, offset_y)
    if blur > 0:
        shadow = _gaussian_blur_rgba(shadow, blur)
    return _alpha_composite(shadow, pixels)


def apply_inner_shadow(pixels: np.ndarray, color: tuple, offset_x: int,
                       offset_y: int, blur: int, opacity: float,
                       original_alpha: np.ndarray | None = None) -> np.ndarray:
    h, w = pixels.shape[:2]
    orig_alpha = original_alpha if original_alpha is not None else pixels[:, :, 3]
    inv_mask = orig_alpha == 0
    shadow = np.zeros((h, w, 4), dtype=np.uint8)
    shadow_color = list(color[:3]) + [int(255 * opacity)]
    shadow[inv_mask] = shadow_color
    shadow = _shift_array(shadow, offset_x, offset_y)
    if blur > 0:
        shadow = _gaussian_blur_rgba(shadow, blur)
    shadow[orig_alpha == 0] = [0, 0, 0, 0]
    return _alpha_composite(pixels, shadow)


# ---------- COLOR EFFECTS ----------

def apply_hue_sat(pixels: np.ndarray, hue: int, saturation: float,
                  value: int) -> np.ndarray:
    result = pixels.copy()
    opaque = pixels[:, :, 3] > 0
    if not np.any(opaque):
        return result

    rgb = pixels[:, :, :3].astype(np.float32) / 255.0
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin

    h_arr = np.zeros_like(cmax)
    mask_r = (cmax == r) & (delta > 0)
    mask_g = (cmax == g) & (delta > 0) & ~mask_r
    mask_b = (cmax == b) & (delta > 0) & ~mask_r & ~mask_g
    h_arr[mask_r] = (((g[mask_r] - b[mask_r]) / delta[mask_r]) % 6) / 6.0
    h_arr[mask_g] = (((b[mask_g] - r[mask_g]) / delta[mask_g]) + 2) / 6.0
    h_arr[mask_b] = (((r[mask_b] - g[mask_b]) / delta[mask_b]) + 4) / 6.0

    s_arr = np.where(cmax > 0, delta / cmax, 0.0)
    v_arr = cmax

    h_arr = (h_arr + hue / 360.0) % 1.0
    s_arr = np.clip(s_arr * saturation, 0.0, 1.0)
    v_arr = np.clip(v_arr + value / 255.0, 0.0, 1.0)

    h6 = h_arr * 6.0
    i = h6.astype(np.int32) % 6
    f = h6 - np.floor(h6)
    p = v_arr * (1 - s_arr)
    q = v_arr * (1 - f * s_arr)
    t = v_arr * (1 - (1 - f) * s_arr)

    nr = np.where(i == 0, v_arr, np.where(i == 1, q, np.where(i == 2, p,
         np.where(i == 3, p, np.where(i == 4, t, v_arr)))))
    ng = np.where(i == 0, t, np.where(i == 1, v_arr, np.where(i == 2, v_arr,
         np.where(i == 3, q, np.where(i == 4, p, p)))))
    nb = np.where(i == 0, p, np.where(i == 1, p, np.where(i == 2, t,
         np.where(i == 3, v_arr, np.where(i == 4, v_arr, q)))))

    result[opaque, 0] = (nr[opaque] * 255).astype(np.uint8)
    result[opaque, 1] = (ng[opaque] * 255).astype(np.uint8)
    result[opaque, 2] = (nb[opaque] * 255).astype(np.uint8)

    return result


def apply_gradient_map(pixels: np.ndarray, stops: list,
                       opacity: float) -> np.ndarray:
    result = pixels.copy()
    lum = (0.299 * pixels[:, :, 0].astype(np.float32) +
           0.587 * pixels[:, :, 1].astype(np.float32) +
           0.114 * pixels[:, :, 2].astype(np.float32)) / 255.0

    opaque = pixels[:, :, 3] > 0
    stops = sorted(stops, key=lambda s: s[0])

    lut = np.zeros((256, 4), dtype=np.uint8)
    for i in range(256):
        t = i / 255.0
        below = stops[0]
        above = stops[-1]
        for j in range(len(stops) - 1):
            if stops[j][0] <= t <= stops[j + 1][0]:
                below = stops[j]
                above = stops[j + 1]
                break
        span = above[0] - below[0]
        if span > 0:
            frac = (t - below[0]) / span
        else:
            frac = 0.0
        for c in range(4):
            lut[i, c] = int(below[1][c] + frac * (above[1][c] - below[1][c]))

    lum_idx = (lum * 255).astype(np.uint8)
    mapped = lut[lum_idx]

    if opacity < 1.0:
        blend = opacity
        result[opaque, :3] = (mapped[opaque, :3].astype(np.float32) * blend +
                               pixels[opaque, :3].astype(np.float32) * (1 - blend)).astype(np.uint8)
    else:
        result[opaque, :3] = mapped[opaque, :3]

    return result


# ---------- ADVANCED EFFECTS ----------

def apply_glow(pixels: np.ndarray, threshold: int, radius: int,
               intensity: float, tint: tuple) -> np.ndarray:
    lum = (0.299 * pixels[:, :, 0].astype(np.float32) +
           0.587 * pixels[:, :, 1].astype(np.float32) +
           0.114 * pixels[:, :, 2].astype(np.float32))
    bright_mask = (lum > threshold) & (pixels[:, :, 3] > 0)

    bright = np.zeros_like(pixels)
    bright[bright_mask] = pixels[bright_mask]

    if tint != (255, 255, 255, 255):
        tint_arr = np.array(tint[:3], dtype=np.float32) / 255.0
        bright[bright_mask, 0] = (bright[bright_mask, 0] * tint_arr[0]).astype(np.uint8)
        bright[bright_mask, 1] = (bright[bright_mask, 1] * tint_arr[1]).astype(np.uint8)
        bright[bright_mask, 2] = (bright[bright_mask, 2] * tint_arr[2]).astype(np.uint8)

    blurred = _gaussian_blur_rgba(bright, radius)

    if intensity != 1.0:
        blurred[:, :, :3] = np.clip(
            blurred[:, :, :3].astype(np.float32) * intensity, 0, 255
        ).astype(np.uint8)

    result = pixels.copy()
    blend_arr = np.array(result, dtype=np.uint8)
    screen = apply_blend_mode(blend_arr, blurred, "screen")
    glow_alpha = blurred[:, :, 3].astype(np.float32) / 255.0
    for c in range(3):
        result[:, :, c] = (
            result[:, :, c] * (1 - glow_alpha) +
            screen[:, :, c] * glow_alpha
        ).astype(np.uint8)
    result[:, :, 3] = np.maximum(result[:, :, 3], blurred[:, :, 3])

    return result


def _generate_pattern(name: str, size: int = 4) -> np.ndarray:
    p = np.zeros((size, size, 4), dtype=np.uint8)
    if name == "scanlines":
        for y in range(size):
            val = 255 if y % 2 == 0 else 0
            p[y, :] = [val, val, val, 255]
    elif name == "checkerboard":
        for y in range(size):
            for x in range(size):
                val = 255 if (x + y) % 2 == 0 else 0
                p[y, x] = [val, val, val, 255]
    elif name == "dots":
        p[:, :] = [0, 0, 0, 255]
        p[0, 0] = [255, 255, 255, 255]
    elif name == "crosshatch":
        for y in range(size):
            for x in range(size):
                if y % 2 == 0 or x % 2 == 0:
                    p[y, x] = [255, 255, 255, 255]
                else:
                    p[y, x] = [0, 0, 0, 255]
    elif name == "diagonal":
        for y in range(size):
            for x in range(size):
                val = 255 if (x + y) % 3 == 0 else 0
                p[y, x] = [val, val, val, 255]
    elif name == "noise":
        rng = np.random.RandomState(42)
        vals = rng.randint(0, 256, (size, size), dtype=np.uint8)
        p[:, :, 0] = vals
        p[:, :, 1] = vals
        p[:, :, 2] = vals
        p[:, :, 3] = 255
    return p


def apply_pattern_overlay(pixels: np.ndarray, pattern: str, blend_mode: str,
                          opacity: float, scale: int, offset_x: int,
                          offset_y: int) -> np.ndarray:
    h, w = pixels.shape[:2]
    pat = _generate_pattern(pattern, 4 * scale)
    ph, pw = pat.shape[:2]

    ys = (np.arange(h)[:, None] + offset_y) % ph
    xs = (np.arange(w)[None, :] + offset_x) % pw
    tiled = pat[ys, xs]

    tiled[pixels[:, :, 3] == 0] = [0, 0, 0, 0]
    tiled[:, :, 3] = (tiled[:, :, 3].astype(np.float32) * opacity).astype(np.uint8)

    if blend_mode == "normal":
        return _alpha_composite(pixels, tiled)
    else:
        blended = apply_blend_mode(pixels, tiled, blend_mode)
        pat_alpha = tiled[:, :, 3].astype(np.float32) / 255.0
        result = pixels.copy()
        for c in range(3):
            result[:, :, c] = (
                pixels[:, :, c] * (1 - pat_alpha) +
                blended[:, :, c] * pat_alpha
            ).astype(np.uint8)
        return result


# ---------- MASTER PIPELINE ----------

EFFECT_FUNCS = {
    "outline": lambda p, **kw: apply_outline(p, **kw),
    "drop_shadow": lambda p, **kw: apply_drop_shadow(p, **kw),
    "inner_shadow": lambda p, **kw: apply_inner_shadow(p, **kw),
    "hue_sat": lambda p, **kw: apply_hue_sat(p, **kw),
    "gradient_map": lambda p, **kw: apply_gradient_map(p, **kw),
    "glow": lambda p, **kw: apply_glow(p, **kw),
    "pattern_overlay": lambda p, **kw: apply_pattern_overlay(p, **kw),
}

EFFECT_ORDER = ["hue_sat", "gradient_map", "pattern_overlay", "glow",
                "inner_shadow", "outline", "drop_shadow"]


def apply_effects(pixels: np.ndarray, effects: list,
                  original_alpha: np.ndarray | None = None) -> np.ndarray:
    if not effects:
        return pixels

    result = pixels.copy()
    if original_alpha is None:
        original_alpha = pixels[:, :, 3].copy()

    enabled = [fx for fx in effects if fx.enabled]
    if not enabled:
        return result

    by_type = {}
    for fx in enabled:
        by_type.setdefault(fx.type, []).append(fx)

    for effect_type in EFFECT_ORDER:
        if effect_type not in by_type:
            continue
        for fx in by_type[effect_type]:
            func = EFFECT_FUNCS.get(fx.type)
            if func:
                if fx.type in ("outline", "drop_shadow", "inner_shadow"):
                    result = func(result, original_alpha=original_alpha, **fx.params)
                else:
                    result = func(result, **fx.params)

    return result
