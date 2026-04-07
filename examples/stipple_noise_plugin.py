"""Stipple Noise — Example RetroSprite plugin.

Demonstrates:
  - PLUGIN_INFO metadata
  - register(api) / unregister(api) lifecycle
  - Registering a filter (Plugins > Filter: Stipple Noise)
  - Registering a custom drawing tool (PluginTool subclass)
  - Subscribing to events (after_draw notification)

Install:
  Copy this file to ~/.retrosprite/plugins/stipple_noise_plugin.py
  and restart RetroSprite. The plugin will appear in the toolbar and
  Plugins menu automatically.
"""
from __future__ import annotations
import random
import numpy as np
from src.plugin_tools import PluginTool

PLUGIN_INFO = {
    "name": "Stipple Noise",
    "author": "RetroSprite Team",
    "version": "1.0",
    "description": "Adds a stipple noise filter and a scatter-dot drawing tool.",
}


# ---------------------------------------------------------------------------
# Filter: randomly scatter dots of the current palette over transparent areas
# ---------------------------------------------------------------------------

def stipple_filter(pixels):
    """Add random stipple dots to transparent pixels.

    Receives a PixelGrid (NumPy ndarray, shape H×W×4 uint8).
    Returns a new PixelGrid with ~8% of transparent pixels filled with
    random semi-transparent dots using the image's existing colors.
    """
    result = pixels.copy()
    h, w = result.shape[:2]

    # Collect unique opaque colors from the image
    opaque_mask = result[:, :, 3] > 0
    if not np.any(opaque_mask):
        return result  # nothing to work with

    colors = result[opaque_mask]
    unique_colors = np.unique(colors.reshape(-1, 4), axis=0)

    # Scatter dots on transparent pixels
    transparent = result[:, :, 3] == 0
    ys, xs = np.where(transparent)
    if len(ys) == 0:
        return result

    density = 0.08  # 8% fill rate
    count = max(1, int(len(ys) * density))
    indices = np.random.choice(len(ys), size=count, replace=False)

    for idx in indices:
        y, x = ys[idx], xs[idx]
        color = unique_colors[np.random.randint(len(unique_colors))].copy()
        color[3] = np.random.randint(80, 200)  # semi-transparent
        result[y, x] = color

    return result


# ---------------------------------------------------------------------------
# Tool: scatter brush — drops random dots around the cursor while drawing
# ---------------------------------------------------------------------------

class ScatterBrushTool(PluginTool):
    """A drawing tool that scatters random dots around the cursor.

    Hold and drag to spray stipple dots in a radius around the pointer.
    Uses the current palette color with random alpha variation.
    """

    name = "Scatter"
    cursor = "spraycan"

    def __init__(self):
        self.radius = 4     # scatter radius in pixels
        self.density = 5    # dots per click/drag event

    def _scatter(self, api, cx, cy):
        """Place random dots around (cx, cy)."""
        layer = api.current_layer()
        if layer is None:
            return
        pixels = layer.pixels
        h, w = pixels.shape[:2]
        color = list(api.palette.selected_color)

        for _ in range(self.density):
            dx = random.randint(-self.radius, self.radius)
            dy = random.randint(-self.radius, self.radius)
            if dx * dx + dy * dy > self.radius * self.radius:
                continue
            x, y = cx + dx, cy + dy
            if 0 <= x < w and 0 <= y < h:
                c = color[:]
                c[3] = random.randint(100, 255)  # random alpha
                pixels[y, x] = c

    def on_click(self, api, x, y):
        api.push_undo("Scatter")
        self._scatter(api, x, y)

    def on_drag(self, api, x, y):
        self._scatter(api, x, y)

    def on_release(self, api, x, y):
        pass


# ---------------------------------------------------------------------------
# Event listener example
# ---------------------------------------------------------------------------

def _on_after_draw(payload):
    """Example event listener — prints a message after each draw action."""
    # In a real plugin you might update a UI widget or run analysis here.
    pass  # silent for production use; uncomment below for debugging:
    # print(f"[Stipple Noise] Draw completed on layer {payload.get('layer', '?')}")


# ---------------------------------------------------------------------------
# Plugin lifecycle
# ---------------------------------------------------------------------------

def register(api):
    """Called by RetroSprite when the plugin is loaded."""
    api.register_filter("Stipple Noise", stipple_filter)
    api.register_tool("Scatter", ScatterBrushTool)
    api.on("after_draw", _on_after_draw)


def unregister(api):
    """Called by RetroSprite when the plugin is unloaded."""
    api.off("after_draw", _on_after_draw)
