"""Layer model for RetroSprite."""
from __future__ import annotations
from uuid import uuid4
import numpy as np
from PIL import Image
from src.pixel_data import PixelGrid, IndexedPixelGrid


class Layer:
    """A single compositing layer containing pixel data and display properties."""

    def __init__(self, name: str, width: int, height: int,
                 color_mode: str = "rgba", palette: list[tuple] | None = None):
        self.name = name
        self.color_mode = color_mode
        if color_mode == "indexed":
            self.pixels = IndexedPixelGrid(width, height, palette)
        else:
            self.pixels = PixelGrid(width, height)
        self.visible: bool = True
        self.opacity: float = 1.0
        self.blend_mode: str = "normal"
        self.locked: bool = False
        self.depth: int = 0
        self.is_group: bool = False
        self.effects: list = []  # list of LayerEffect dicts
        self.cel_id: str = str(uuid4())
        self.clipping: bool = False

    @classmethod
    def from_grid(cls, name: str, grid) -> Layer:
        if hasattr(grid, '_indices'):
            layer = cls(name, grid.width, grid.height,
                        color_mode="indexed", palette=grid._palette)
            layer.pixels = grid.copy()
        else:
            layer = cls(name, grid.width, grid.height)
            layer.pixels._pixels = grid._pixels.copy()
        return layer

    def copy(self) -> Layer:
        palette = self.pixels._palette if self.color_mode == "indexed" else None
        new_layer = Layer(f"{self.name} Copy", self.pixels.width, self.pixels.height,
                          color_mode=self.color_mode, palette=palette)
        if self.color_mode == "indexed":
            new_layer.pixels = self.pixels.copy()
        else:
            new_layer.pixels._pixels = self.pixels._pixels.copy()
        new_layer.visible = self.visible
        new_layer.opacity = self.opacity
        new_layer.blend_mode = self.blend_mode
        new_layer.locked = self.locked
        new_layer.depth = self.depth
        new_layer.is_group = self.is_group
        import copy as copy_mod
        new_layer.effects = copy_mod.deepcopy(self.effects)
        new_layer.cel_id = str(uuid4())
        new_layer.clipping = self.clipping
        return new_layer

    def unlink(self):
        """Make this layer's pixel data independent by deep-copying."""
        self.pixels = self.pixels.copy()
        self.cel_id = str(uuid4())


def apply_blend_mode(base: np.ndarray, blend: np.ndarray, mode: str) -> np.ndarray:
    """Apply blend mode to RGB channels. Both arrays are (H,W,4) uint8.

    Returns a new array with blended RGB and blend's original alpha.
    """
    b = base[:, :, :3].astype(np.int32)
    l = blend[:, :, :3].astype(np.int32)

    if mode == "multiply":
        rgb = (b * l) // 255
    elif mode == "screen":
        rgb = 255 - ((255 - b) * (255 - l)) // 255
    elif mode == "overlay":
        mask = b < 128
        rgb = np.where(mask, (2 * b * l) // 255, 255 - (2 * (255 - b) * (255 - l)) // 255)
    elif mode == "addition":
        rgb = np.minimum(b + l, 255)
    elif mode == "subtract":
        rgb = np.maximum(b - l, 0)
    elif mode == "darken":
        rgb = np.minimum(b, l)
    elif mode == "lighten":
        rgb = np.maximum(b, l)
    elif mode == "difference":
        rgb = np.abs(b - l)
    else:
        # normal or unknown
        rgb = l

    result = blend.copy()
    result[:, :, :3] = rgb.astype(np.uint8)
    return result


def flatten_layers(layers: list[Layer], width: int, height: int) -> PixelGrid:
    """Composite all visible layers into a single PixelGrid.

    Layers are composited bottom-to-top (index 0 = bottom).
    Supports blend modes and layer groups (flat list with depth).
    """
    def _composite_one(base_img, layer_img, blend_mode):
        """Composite a single layer onto base using its blend mode."""
        if blend_mode == "normal":
            return Image.alpha_composite(base_img, layer_img)
        base_arr = np.array(base_img, dtype=np.uint8)
        blend_arr = np.array(layer_img, dtype=np.uint8)
        blended = apply_blend_mode(base_arr, blend_arr, blend_mode)
        blend_alpha = blend_arr[:, :, 3].astype(np.float32) / 255.0
        for c in range(3):
            base_arr[:, :, c] = (
                base_arr[:, :, c] * (1.0 - blend_alpha) +
                blended[:, :, c] * blend_alpha
            ).astype(np.uint8)
        base_a = base_arr[:, :, 3].astype(np.float32) / 255.0
        out_a = base_a + blend_alpha * (1.0 - base_a)
        base_arr[:, :, 3] = (out_a * 255).astype(np.uint8)
        return Image.fromarray(base_arr, "RGBA")

    # Stack-based group compositing
    # Each stack entry: (group_base_image, group_blend_mode, group_opacity, group_visible, group_depth)
    stack = []
    current = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    skip_depth = -1  # if >= 0, skip layers at depth > this
    base_alpha = None  # float32 array (height, width), 0.0-1.0 for clipping masks

    i = 0
    while i < len(layers):
        layer = layers[i]
        depth = layer.depth

        # Check if we're exiting groups (current layer depth decreased or equal)
        while stack and depth <= stack[-1][4]:
            group_base, group_mode, group_opacity, group_visible, group_depth, saved_base_alpha = stack.pop()
            if group_visible:
                if group_opacity < 1.0:
                    arr = np.array(current, dtype=np.uint8)
                    arr[:, :, 3] = (arr[:, :, 3] * group_opacity).astype(np.uint8)
                    current = Image.fromarray(arr, "RGBA")
                current = _composite_one(group_base, current, group_mode)
            else:
                current = group_base
            skip_depth = -1
            base_alpha = saved_base_alpha

        # Skip hidden group children
        if skip_depth >= 0 and depth > skip_depth:
            i += 1
            continue

        if layer.is_group:
            if not layer.visible:
                skip_depth = depth
            else:
                skip_depth = -1
            stack.append((current, layer.blend_mode, layer.opacity, layer.visible, depth, base_alpha))
            base_alpha = None
            current = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            i += 1
            continue

        skip_depth = -1
        if not layer.visible:
            i += 1
            continue

        # Resolve pixel data to RGBA
        if hasattr(layer.pixels, '_indices'):
            layer_rgba = layer.pixels.to_rgba()
        else:
            layer_rgba = layer.pixels._pixels

        if hasattr(layer, 'effects') and layer.effects:
            from src.effects import apply_effects
            raw = layer_rgba.copy()
            original_alpha = raw[:, :, 3].copy()
            processed = apply_effects(raw, layer.effects, original_alpha)
            layer_img = Image.fromarray(processed, "RGBA")
        else:
            layer_img = Image.fromarray(layer_rgba, "RGBA")
        if layer.opacity < 1.0:
            arr = np.array(layer_img, dtype=np.uint8)
            arr[:, :, 3] = (arr[:, :, 3] * layer.opacity).astype(np.uint8)
            layer_img = Image.fromarray(arr, "RGBA")

        # Clipping mask logic
        if getattr(layer, 'clipping', False) and base_alpha is not None:
            # Multiply this layer's alpha by the clip-base's own alpha
            arr = np.array(layer_img, dtype=np.float32)
            arr[:, :, 3] *= base_alpha
            layer_img = Image.fromarray(arr.astype(np.uint8), "RGBA")
        else:
            # This is a normal (non-clipping) layer — capture its alpha as the new clip base
            clip_arr = np.array(layer_img, dtype=np.uint8)
            base_alpha = clip_arr[:, :, 3].astype(np.float32) / 255.0

        current = _composite_one(current, layer_img, layer.blend_mode)
        i += 1

    # Pop remaining groups
    while stack:
        group_base, group_mode, group_opacity, group_visible, group_depth, saved_base_alpha = stack.pop()
        if group_visible:
            if group_opacity < 1.0:
                arr = np.array(current, dtype=np.uint8)
                arr[:, :, 3] = (arr[:, :, 3] * group_opacity).astype(np.uint8)
                current = Image.fromarray(arr, "RGBA")
            current = _composite_one(group_base, current, group_mode)
        else:
            current = group_base

    return PixelGrid.from_pil_image(current)
