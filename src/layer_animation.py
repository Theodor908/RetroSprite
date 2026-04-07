"""Layer management, animation playback, and image filters mixin for RetroSprite."""
from __future__ import annotations

from tkinter import simpledialog

from src.image_processing import (
    blur, scale, rotate, flip_horizontal, flip_vertical,
    adjust_brightness, adjust_contrast, posterize
)


class LayerAnimationMixin:
    """Layers, frames, animation playback, onion skin, tags, image filters,
    color mode conversion, and effects dialog."""

    # --- Gradient Fill ---

    def _apply_gradient_fill(self):
        """Apply gradient fill to the active layer using primary colors."""
        layer_grid = self.timeline.current_layer()
        color1 = self.palette.colors[0] if self.palette.colors else (0, 0, 0, 255)
        color2 = self.palette.selected_color
        self._push_undo()
        self._tools["GradientFill"].apply(
            layer_grid, 0, 0, layer_grid.width - 1, 0, color1, color2)
        self._render_canvas()
        self._update_status("Gradient fill applied")

    # --- Color Mode Conversion ---

    def _convert_to_indexed(self):
        """Convert project from RGBA to indexed color mode."""
        if getattr(self.timeline, 'color_mode', 'rgba') == "indexed":
            self._update_status("Already in indexed mode")
            return
        self._push_undo()
        self.api.convert_to_indexed()
        self.right_panel.palette_panel.refresh()
        self._refresh_all()
        self._update_status("Converted to indexed color mode")

    def _convert_to_rgba(self):
        """Convert project from indexed to RGBA color mode."""
        if getattr(self.timeline, 'color_mode', 'rgba') == "rgba":
            self._update_status("Already in RGBA mode")
            return
        self._push_undo()
        self.api.convert_to_rgba()
        self._refresh_all()
        self._update_status("Converted to RGBA color mode")

    # --- Frame Management ---

    def _on_frame_select(self, index):
        self.timeline.set_current(index)
        self.api.emit("frame_change", {
            "frame_index": index,
            "frame": self.timeline.current_frame_obj()
        })
        self._refresh_canvas()
        self._update_frame_list()
        self._update_layer_list()
        self.timeline_panel.refresh()

    def _add_frame(self):
        self.timeline.add_frame()
        self.timeline.set_current(self.timeline.frame_count - 1)
        self.api.emit("frame_added", {"frame_index": self.timeline.frame_count - 1})
        self._refresh_canvas()
        self._update_frame_list()
        self.timeline_panel.refresh()

    def _insert_frame(self, after_index=None):
        if after_index is None:
            after_index = self.timeline.current_index
        self.timeline.insert_frame(after_index)
        self.timeline.set_current(after_index + 1)
        self._refresh_canvas()
        self._update_frame_list()
        self.timeline_panel.refresh()

    def _duplicate_frame(self):
        self.timeline.duplicate_frame(self.timeline.current_index)
        self.timeline.set_current(self.timeline.current_index + 1)
        self._refresh_canvas()
        self._update_frame_list()
        self.timeline_panel.refresh()

    def _delete_frame(self):
        idx = self.timeline.current_index
        self.timeline.remove_frame(idx)
        self.api.emit("frame_removed", {"frame_index": idx})
        self._refresh_canvas()
        self._update_frame_list()
        self.timeline_panel.refresh()

    # --- Layer Management ---

    def _on_layer_select(self, index):
        frame_obj = self.timeline.current_frame_obj()
        if 0 <= index < len(frame_obj.layers):
            self.timeline.set_active_layer_all(index)
            self.api.emit("layer_change", {
                "layer_index": index,
                "layer": frame_obj.layers[index]
            })
            self._refresh_canvas()
            self._update_layer_list()
            self.timeline_panel.refresh()
            # Show/hide tiles panel based on selected layer type
            self.right_panel.update_tiles_visibility(frame_obj.layers[index])

    def _add_layer(self):
        self.timeline.add_layer_to_all()
        frame_obj = self.timeline.current_frame_obj()
        self.api.emit("layer_added", {
            "layer_index": frame_obj.active_layer_index,
            "layer": frame_obj.active_layer
        })
        self._refresh_canvas()
        self._update_layer_list()
        self.timeline_panel.refresh()

    def _add_group(self):
        """Add a new layer group."""
        frame_obj = self.timeline.current_frame_obj()
        name = f"Group {len(frame_obj.layers)}"
        self.timeline.add_group_to_all(name, depth=0)
        self._refresh_canvas()
        self._update_layer_list()
        self.timeline_panel.refresh()

    def _delete_layer(self):
        frame_obj = self.timeline.current_frame_obj()
        idx = frame_obj.active_layer_index
        self.timeline.remove_layer_from_all(idx)
        self.api.emit("layer_removed", {"layer_index": idx})
        self._refresh_canvas()
        self._update_layer_list()
        self.timeline_panel.refresh()

    def _duplicate_layer(self):
        frame_obj = self.timeline.current_frame_obj()
        self.timeline.duplicate_layer_in_all(frame_obj.active_layer_index)
        self._refresh_canvas()
        self._update_layer_list()
        self.timeline_panel.refresh()

    def _merge_down_layer(self):
        frame_obj = self.timeline.current_frame_obj()
        idx = frame_obj.active_layer_index
        self.timeline.merge_down_in_all(idx)
        self.api.emit("layer_merged", {"layer_index": idx})
        self._refresh_canvas()
        self._update_layer_list()
        self.timeline_panel.refresh()

    def _toggle_layer_visibility(self):
        frame_obj = self.timeline.current_frame_obj()
        idx = frame_obj.active_layer_index
        self._on_layer_visibility_idx(idx)
        self.timeline_panel.refresh()

    def _on_layer_visibility_idx(self, index):
        """Toggle visibility of a specific layer by index (all frames).

        If the layer is a group, propagates to all children.
        """
        frame_obj = self.timeline.current_frame_obj()
        if 0 <= index < len(frame_obj.layers):
            new_vis = not frame_obj.layers[index].visible
            # Collect indices to toggle: the layer itself + children if group
            targets = [index]
            if frame_obj.layers[index].is_group:
                g_depth = frame_obj.layers[index].depth
                for ci in range(index + 1, len(frame_obj.layers)):
                    if frame_obj.layers[ci].is_group or frame_obj.layers[ci].depth <= g_depth:
                        break
                    targets.append(ci)
            for frame in self.timeline._frames:
                for ti in targets:
                    if 0 <= ti < len(frame.layers):
                        frame.layers[ti].visible = new_vis
            self._refresh_canvas()
            self._update_layer_list()

    def _on_layer_lock(self, index):
        """Toggle lock on a specific layer by index (all frames).

        If the layer is a group, propagates to all children.
        """
        frame_obj = self.timeline.current_frame_obj()
        if 0 <= index < len(frame_obj.layers):
            new_lock = not frame_obj.layers[index].locked
            targets = [index]
            if frame_obj.layers[index].is_group:
                g_depth = frame_obj.layers[index].depth
                for ci in range(index + 1, len(frame_obj.layers)):
                    if frame_obj.layers[ci].is_group or frame_obj.layers[ci].depth <= g_depth:
                        break
                    targets.append(ci)
            for frame in self.timeline._frames:
                for ti in targets:
                    if 0 <= ti < len(frame.layers):
                        frame.layers[ti].locked = new_lock

    def _on_opacity_change(self, value):
        frame_obj = self.timeline.current_frame_obj()
        frame_obj.active_layer.opacity = value / 100
        self._refresh_canvas()

    def _on_blend_mode_change(self, index, mode):
        """Set blend mode for layer at index across all frames."""
        for frame in self.timeline._frames:
            if index < len(frame.layers):
                frame.layers[index].blend_mode = mode
        self._render_canvas()

    def _rename_layer(self, index: int):
        frame_obj = self.timeline.current_frame_obj()
        if 0 <= index < len(frame_obj.layers):
            layer = frame_obj.layers[index]
            new_name = simpledialog.askstring(
                "Rename Layer", "Layer name:", initialvalue=layer.name,
                parent=self.root)
            if new_name is not None and new_name.strip():
                for frame in self.timeline._frames:
                    if 0 <= index < len(frame.layers):
                        frame.layers[index].name = new_name.strip()
                self._update_layer_list()
                self.timeline_panel.refresh()

    def _rename_frame(self, index: int):
        frame_obj = self.timeline.get_frame_obj(index)
        current_name = frame_obj.name or f"Frame {index + 1}"
        new_name = simpledialog.askstring(
            "Rename Frame", "Frame name:", initialvalue=current_name,
            parent=self.root)
        if new_name is not None and new_name.strip():
            frame_obj.name = new_name.strip()
            self._update_frame_list()

    def _update_layer_list(self):
        # Layer list is managed by the timeline panel now
        pass

    def _update_frame_list(self):
        # Frame list is managed by the timeline panel now
        pass

    # --- Image Processing ---

    def _apply_filter(self, filter_name: str):
        grid = self.timeline.current_layer()

        filters = {
            "blur": lambda g: blur(g, radius=1),
            "scale_up": lambda g: scale(g, 2.0),
            "scale_down": lambda g: scale(g, 0.5),
            "rotate_90": lambda g: rotate(g, 90),
            "rotate_180": lambda g: rotate(g, 180),
            "flip_h": flip_horizontal,
            "flip_v": flip_vertical,
            "bright_up": lambda g: adjust_brightness(g, 1.3),
            "bright_down": lambda g: adjust_brightness(g, 0.7),
            "contrast_up": lambda g: adjust_contrast(g, 1.5),
            "contrast_down": lambda g: adjust_contrast(g, 0.7),
            "posterize": lambda g: posterize(g, levels=4),
        }

        fn = filters.get(filter_name)
        if fn:
            self._push_undo()
            result = fn(grid)
            frame_obj = self.timeline.current_frame_obj()
            frame_obj.active_layer.pixels = result
            self._refresh_canvas()

    # --- Animation ---

    def _play_animation(self):
        if self._playing:
            return
        self._playing = True
        self._animate_step(0)

    def _animate_step(self, frame_idx):
        if not self._playing:
            return
        fc = self.timeline.frame_count

        if self._playback_mode == "forward":
            if frame_idx >= fc:
                frame_idx = 0
        elif self._playback_mode == "reverse":
            if frame_idx < 0:
                frame_idx = fc - 1
        elif self._playback_mode == "pingpong":
            if frame_idx >= fc:
                self._pingpong_direction = -1
                frame_idx = max(fc - 2, 0)
            elif frame_idx < 0:
                self._pingpong_direction = 1
                frame_idx = min(1, fc - 1)

        self.timeline.set_current(frame_idx)
        self._refresh_canvas()
        self._update_frame_list()
        self.timeline_panel.highlight_frame(frame_idx)
        self.right_panel.animation_preview.render_frame(
            self.timeline.current_frame()
        )
        # Use per-frame duration if available, else fallback to preview spinbox
        frame_obj = self.timeline.current_frame_obj()
        delay = getattr(frame_obj, 'duration_ms', None) or \
            self.right_panel.animation_preview.frame_duration_ms

        if self._playback_mode == "reverse":
            next_idx = frame_idx - 1
        elif self._playback_mode == "pingpong":
            next_idx = frame_idx + self._pingpong_direction
        else:
            next_idx = frame_idx + 1

        self._play_after_id = self.root.after(
            delay, self._animate_step, next_idx
        )

    def _stop_animation(self):
        self._playing = False
        if self._play_after_id:
            self.root.after_cancel(self._play_after_id)
            self._play_after_id = None

    def _cycle_playback_mode(self):
        """Cycle forward -> reverse -> pingpong -> forward."""
        modes = ["forward", "reverse", "pingpong"]
        idx = modes.index(self._playback_mode)
        self._playback_mode = modes[(idx + 1) % len(modes)]
        self._pingpong_direction = 1
        self.right_panel.animation_preview.update_playback_label(
            self._playback_mode)
        self._update_status(f"Playback: {self._playback_mode}")

    def _on_playback_mode_change(self, mode: str):
        """Called when playback mode is changed from the timeline panel."""
        self._playback_mode = mode
        self._pingpong_direction = 1
        self._update_status(f"Playback: {mode}")

    def _on_onion_toggle_from_timeline(self, on: bool):
        """Called when onion skin is toggled from the timeline panel."""
        self._onion_skin = on
        self._render_canvas()
        self._update_status()

    def _on_onion_range_change(self, range_val: int):
        """Called when onion skin range is changed from the timeline panel."""
        self._onion_range = range_val
        if self._onion_skin:
            self._render_canvas()

    def _toggle_onion_skin(self):
        self._onion_skin = not self._onion_skin
        self._render_canvas()

    # --- Frame Tags ---

    def _add_tag_dialog(self):
        """Open a dialog to add a frame tag."""
        from src.ui.tag_dialog import TagDialog
        dialog = TagDialog(self.root, self.timeline.frame_count)
        self.root.wait_window(dialog)
        if dialog.result is not None:
            self.timeline.add_tag(
                dialog.result["name"], dialog.result["color"],
                dialog.result["start"], dialog.result["end"])
            self._update_frame_list()
            self.timeline_panel.refresh()
            self._update_status(f"Tag '{dialog.result['name']}' added")

    # --- Layer Effects ---

    def _on_layer_fx_click(self, layer_index: int):
        """Open the EffectsDialog for the given layer index."""
        from src.ui.effects_dialog import EffectsDialog
        frame_obj = self.timeline.current_frame_obj()
        if layer_index < 0 or layer_index >= len(frame_obj.layers):
            return
        layer = frame_obj.layers[layer_index]
        EffectsDialog(self.root, layer, self._render_canvas, api=self.api)
        # After dialog closes, refresh timeline to update FX button color
        self.timeline_panel.refresh()

    def _on_display_effects_toggle(self):
        """Toggle display of layer effects in the canvas."""
        self._display_effects = self._display_effects_var.get()
        self._render_canvas()
