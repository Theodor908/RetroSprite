"""Scripting API for RetroSprite — plugin and CLI interface."""
from __future__ import annotations
import traceback
from typing import Any, Callable

from src.animation import AnimationTimeline, Frame
from src.layer import Layer
from src.palette import Palette
from src.pixel_data import PixelGrid


class RetroSpriteAPI:
    """Central API object for plugins and scripts.

    Provides direct access to internals and high-level convenience methods.
    When app is None (CLI/headless mode), UI registration methods are no-ops.
    """

    def __init__(self, timeline: AnimationTimeline, palette: Palette,
                 app: Any | None = None):
        self.timeline = timeline
        self.palette = palette
        self.app = app
        self._listeners: dict[str, list[Callable]] = {}
        self._plugin_tools: dict[str, Any] = {}
        self._plugin_filters: dict[str, Callable] = {}
        self._plugin_effects: dict[str, dict] = {}
        self._menu_items: list[dict] = []

    # --- Event System ---

    def on(self, event_name: str, callback: Callable) -> None:
        """Subscribe to an event."""
        self._listeners.setdefault(event_name, []).append(callback)

    def off(self, event_name: str, callback: Callable) -> None:
        """Unsubscribe from an event."""
        if event_name in self._listeners:
            try:
                self._listeners[event_name].remove(callback)
            except ValueError:
                pass

    def emit(self, event_name: str, payload: dict) -> bool:
        """Fire event. Returns False if any before_* listener returned False."""
        for cb in self._listeners.get(event_name, []):
            try:
                result = cb(payload)
                if event_name.startswith("before_") and result is False:
                    return False
            except Exception:
                traceback.print_exc()
        return True

    # --- Convenience: Project I/O ---

    def load_project(self, path: str) -> None:
        from src.project import load_project as _load
        timeline, palette, _, _, _ = _load(path)
        self.timeline = timeline
        self.palette = palette

    def save_project(self, path: str) -> None:
        from src.project import save_project as _save
        _save(path, self.timeline, self.palette)

    def new_project(self, width: int, height: int, fps: int = 12) -> None:
        self.timeline = AnimationTimeline(width, height)
        self.timeline.fps = fps
        self.palette = Palette("Pico-8")

    # --- Convenience: Export ---

    def export_png(self, path: str, frame: int = 0, scale: int = 1,
                   layer: int | str | None = None) -> None:
        from src.export import export_png_single
        export_png_single(self.timeline, path, frame=frame, scale=scale,
                          layer=layer)

    def export_gif(self, path: str, scale: int = 1) -> None:
        self.timeline.export_gif(path, fps=self.timeline.fps, scale=scale)

    def export_sheet(self, path: str, scale: int = 1,
                     columns: int = 0) -> str:
        from src.export import save_sprite_sheet
        return save_sprite_sheet(self.timeline, path, scale=scale,
                                 columns=columns)

    def export_webp(self, path: str, scale: int = 1) -> None:
        """Export animation as lossless WebP."""
        from src.animated_export import export_webp as _export_webp
        _export_webp(self.timeline, path, scale=scale)

    def export_apng(self, path: str, scale: int = 1) -> None:
        """Export animation as APNG."""
        from src.animated_export import export_apng as _export_apng
        _export_apng(self.timeline, path, scale=scale)

    def export_frames(self, path: str, scale: int = 1, layer=None) -> list[str]:
        """Export each frame as a numbered PNG."""
        from src.export import export_png_sequence
        return export_png_sequence(self.timeline, path, scale, layer)

    # --- Convenience: Frame/Layer Access ---

    def current_frame_pixels(self) -> PixelGrid:
        return self.timeline.current_frame()

    def current_layer(self) -> Layer:
        return self.timeline.current_frame_obj().active_layer

    def get_frame(self, index: int) -> Frame:
        return self.timeline.get_frame_obj(index)

    def add_frame(self) -> Frame:
        self.timeline.add_frame()
        return self.timeline.get_frame_obj(self.timeline.frame_count - 1)

    def add_layer(self, name: str) -> Layer:
        self.timeline.add_layer_to_all(name)
        return self.timeline.current_frame_obj().active_layer

    def remove_frame(self, index: int) -> None:
        self.timeline.remove_frame(index)

    def remove_layer(self, index: int) -> None:
        self.timeline.remove_layer_from_all(index)

    # --- Convenience: Image Processing ---

    def apply_filter(self, func: Callable[[PixelGrid], PixelGrid],
                     frame: int | None = None,
                     layer: int | None = None) -> None:
        self.push_undo("Apply Filter")
        f_idx = frame if frame is not None else self.timeline.current_index
        frame_obj = self.timeline.get_frame_obj(f_idx)
        l_idx = layer if layer is not None else frame_obj.active_layer_index
        target_layer = frame_obj.layers[l_idx]

        # Selection-aware: if GUI has a selection, apply only to selected pixels
        selection = None
        if self.app is not None:
            selection = getattr(self.app, '_selection_pixels', None)

        if selection:
            import numpy as np
            pixels = target_layer.pixels
            xs = [p[0] for p in selection]
            ys = [p[1] for p in selection]
            x0, x1 = min(xs), max(xs) + 1
            y0, y1 = min(ys), max(ys) + 1
            if hasattr(pixels, '_indices'):
                full_pg = pixels.to_pixelgrid()
            else:
                full_pg = pixels
            sub = PixelGrid(x1 - x0, y1 - y0)
            sub._pixels = full_pg._pixels[y0:y1, x0:x1].copy()
            result_sub = func(sub)
            for sx, sy in selection:
                lx, ly = sx - x0, sy - y0
                if 0 <= lx < result_sub.width and 0 <= ly < result_sub.height:
                    color = tuple(int(v) for v in result_sub._pixels[ly, lx])
                    pixels.set_pixel(sx, sy, color)
        else:
            if hasattr(target_layer.pixels, '_indices'):
                pg = target_layer.pixels.to_pixelgrid()
                result = func(pg)
                for y in range(result.height):
                    for x in range(result.width):
                        color = result.get_pixel(x, y)
                        if color:
                            target_layer.pixels.set_pixel(x, y, color)
            else:
                result = func(target_layer.pixels)
                target_layer.pixels._pixels = result._pixels.copy()

    def apply_effect(self, layer_index: int, effect_type: str,
                     params: dict) -> None:
        self.push_undo("Apply Effect")
        from src.effects import LayerEffect
        frame_obj = self.timeline.current_frame_obj()
        layer = frame_obj.layers[layer_index]
        effect = LayerEffect(effect_type, params)
        layer.effects.append(effect)

    # --- Undo (GUI mode only, no-op in headless) ---

    def push_undo(self, label: str = "Script Action") -> None:
        if self.app is not None and hasattr(self.app, '_push_undo'):
            self.app._push_undo()

    # --- Plugin Registration ---

    def register_menu_item(self, label: str, callback: Callable,
                           submenu: str = "Plugins") -> None:
        if self.app is None:
            import warnings
            warnings.warn("register_menu_item is a no-op in headless mode")
            return
        self._menu_items.append({
            "label": label, "callback": callback, "submenu": submenu
        })

    def register_filter(self, name: str,
                        func: Callable[[PixelGrid], PixelGrid]) -> None:
        self._plugin_filters[name] = func

    def register_tool(self, name: str, tool_class: type) -> None:
        self._plugin_tools[name] = tool_class
        if self.app is None:
            import warnings
            warnings.warn("register_tool: tool UI unavailable in headless mode")

    def register_effect(self, name: str, apply_func: Callable,
                        default_params: dict) -> None:
        self._plugin_effects[name] = {
            "apply_func": apply_func,
            "default_params": default_params,
        }

    # --- Color Mode Conversion ---

    def convert_to_indexed(self, num_colors: int | None = None) -> None:
        """Convert project from RGBA to indexed color mode."""
        from src.quantize import median_cut, quantize_to_palette
        from src.pixel_data import IndexedPixelGrid
        import numpy as np

        if num_colors is not None:
            # Gather all pixels for median cut
            all_pixels = []
            for i in range(self.timeline.frame_count):
                frame = self.timeline.get_frame_obj(i)
                for layer in frame.layers:
                    if hasattr(layer, 'is_tilemap') and layer.is_tilemap():
                        continue
                    if getattr(layer, 'color_mode', 'rgba') == "indexed":
                        continue
                    all_pixels.append(layer.pixels._pixels.reshape(-1, 4))
            if all_pixels:
                combined = np.vstack(all_pixels)
                new_colors = median_cut(combined, num_colors)
                self.palette.colors.clear()
                self.palette.colors.extend(new_colors)

        palette_colors = self.palette.colors
        self.timeline.palette_ref = palette_colors
        for i in range(self.timeline.frame_count):
            frame = self.timeline.get_frame_obj(i)
            for j, layer in enumerate(frame.layers):
                if hasattr(layer, 'is_tilemap') and layer.is_tilemap():
                    continue
                if getattr(layer, 'color_mode', 'rgba') == "indexed":
                    continue
                indexed = quantize_to_palette(layer.pixels, palette_colors)
                layer.pixels = indexed
                layer.color_mode = "indexed"
        self.timeline.color_mode = "indexed"

    def convert_to_rgba(self) -> None:
        """Convert project from indexed to RGBA color mode."""
        palette_colors = self.palette.colors
        for i in range(self.timeline.frame_count):
            frame = self.timeline.get_frame_obj(i)
            for j, layer in enumerate(frame.layers):
                if hasattr(layer, 'is_tilemap') and layer.is_tilemap():
                    continue
                if getattr(layer, 'color_mode', 'rgba') != "indexed":
                    continue
                rgba_grid = layer.pixels.to_pixelgrid(palette_colors)
                layer.pixels = rgba_grid
                layer.color_mode = "rgba"
        self.timeline.color_mode = "rgba"
        self.timeline.palette_ref = None
