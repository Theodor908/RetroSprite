"""PSD file import for RetroSprite using psd-tools."""
from __future__ import annotations
import numpy as np
from PIL import Image

from src.animation import AnimationTimeline, Frame
from src.layer import Layer
from src.palette import Palette

# Map PSD blend mode names to RetroSprite blend mode names.
# psd-tools exposes blend_mode.name which is the human-readable form (lowercase).
PSD_BLEND_MAP = {
    "normal": "normal",
    "multiply": "multiply",
    "screen": "screen",
    "overlay": "overlay",
    "darken": "darken",
    "lighten": "lighten",
    "difference": "difference",
    "linear dodge": "addition",
    "subtract": "subtract",
}


def _extract_palette(layers_pixels: list[np.ndarray], max_colors: int = 256) -> list[tuple]:
    """Extract unique opaque colors from layer pixel arrays, capped at max_colors."""
    colors = set()
    for pixels in layers_pixels:
        if pixels is None:
            continue
        flat = pixels.reshape(-1, 4)
        opaque = flat[flat[:, 3] > 0]
        for row in opaque:
            colors.add(tuple(int(v) for v in row))
            if len(colors) >= max_colors:
                return list(colors)[:max_colors]
    return list(colors) if colors else [(0, 0, 0, 255)]


def load_psd(path: str) -> tuple[AnimationTimeline, Palette]:
    """Open a .psd and convert its layers into a single-frame timeline.
    Groups become is_group layers, blend modes are mapped where possible."""
    from psd_tools import PSDImage

    psd = PSDImage.open(path)
    width, height = psd.width, psd.height

    timeline = AnimationTimeline(width, height)
    frame = timeline.get_frame_obj(0)
    # Remove the default empty layer — we'll add PSD layers
    frame.layers.clear()

    layers_pixels = []

    def _process_layers(psd_layers, depth=0):
        """Recursively process PSD layers."""
        for psd_layer in psd_layers:
            if psd_layer.is_group():
                # Create a group layer
                group = Layer(psd_layer.name, width, height)
                group.is_group = True
                group.depth = depth
                group.visible = psd_layer.is_visible()
                group.opacity = psd_layer.opacity / 255.0
                frame.layers.append(group)
                # Process children at deeper depth
                _process_layers(psd_layer, depth + 1)
            else:
                # Create a regular layer
                layer = Layer(psd_layer.name, width, height)
                layer.visible = psd_layer.is_visible()
                layer.opacity = psd_layer.opacity / 255.0

                # Map blend mode
                blend_name = psd_layer.blend_mode.name
                # psd-tools uses underscored names; normalize
                blend_name = blend_name.replace("_", " ").lower()
                layer.blend_mode = PSD_BLEND_MAP.get(blend_name, "normal")

                # Extract pixel data
                try:
                    pil_img = psd_layer.topil()
                    if pil_img is not None:
                        pil_img = pil_img.convert("RGBA")
                        # PSD layers can have offsets — paste into full-size canvas
                        full = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                        full.paste(pil_img, (psd_layer.left, psd_layer.top))
                        pixels = np.array(full, dtype=np.uint8)
                        layer.pixels._pixels = pixels
                        layers_pixels.append(pixels)
                except Exception:
                    # Failed to extract pixels — leave layer empty
                    pass

                layer.depth = depth
                frame.layers.append(layer)

    _process_layers(psd)

    # If no layers were found (e.g., flat PSD), use composite
    if not frame.layers:
        layer = Layer("Background", width, height)
        composite = psd.composite().convert("RGBA")
        pixels = np.array(composite, dtype=np.uint8)
        layer.pixels._pixels = pixels
        layers_pixels.append(pixels)
        frame.layers.append(layer)

    frame.active_layer_index = 0

    # Extract palette
    palette = Palette("Imported")
    extracted = _extract_palette(layers_pixels)
    palette.colors.clear()
    palette.colors.extend(extracted)

    return timeline, palette
