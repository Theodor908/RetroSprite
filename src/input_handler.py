"""Canvas input handling mixin for RetroSprite (click, drag, release, tool dispatch)."""
from __future__ import annotations

import math
import tkinter as tk

import numpy as np

from src.pixel_data import PixelGrid


def _shift_grid(grid, dx: int, dy: int):
    """Return a new grid (same type) with all pixels shifted by (dx, dy).
    Works for both PixelGrid (RGBA) and IndexedPixelGrid."""
    result = grid.copy()
    if hasattr(grid, '_indices'):
        arr = grid._indices
        new_arr = np.zeros_like(arr)
    else:
        arr = grid._pixels
        new_arr = np.zeros_like(arr)
    h, w = arr.shape[:2]
    src_x0 = max(0, -dx)
    src_x1 = min(w, w - dx)
    src_y0 = max(0, -dy)
    src_y1 = min(h, h - dy)
    dst_x0 = max(0, dx)
    dst_x1 = min(w, w + dx)
    dst_y0 = max(0, dy)
    dst_y1 = min(h, h + dy)
    if src_x0 < src_x1 and src_y0 < src_y1:
        new_arr[dst_y0:dst_y1, dst_x0:dst_x1] = arr[src_y0:src_y1, src_x0:src_x1]
    if hasattr(result, '_indices'):
        result._indices = new_arr
    else:
        result._pixels = new_arr
    return result


def _hit_test_symmetry_axis(canvas_x: int, canvas_y: int,
                             mode: str, axis_x: int, axis_y: int,
                             pixel_size: int, threshold: float = 6.0) -> str | None:
    """Test if canvas coordinates are near a symmetry axis line.

    Returns: "x" if near vertical axis, "y" if near horizontal axis, None otherwise.
    """
    if mode == "off":
        return None
    thresh_grid = threshold / pixel_size if pixel_size > 0 else threshold

    if mode in ("horizontal", "both"):
        if abs(canvas_x - axis_x) <= thresh_grid:
            return "x"
    if mode in ("vertical", "both"):
        if abs(canvas_y - axis_y) <= thresh_grid:
            return "y"
    return None


class InputHandlerMixin:
    """Handles mouse input on the canvas — click, drag, release, tool dispatch,
    selection ops, clipboard, and polygon/brush management."""

    def _on_canvas_click(self, x, y, event_state=0):
        # Alt+click starts reference image drag
        alt_held = bool(event_state & 0x20000)
        if alt_held and self._reference is not None:
            self._ref_begin_drag(x, y)
            return

        # Symmetry axis drag
        if self._symmetry_mode != "off":
            axis_hit = _hit_test_symmetry_axis(
                x, y, self._symmetry_mode,
                self._symmetry_axis_x, self._symmetry_axis_y,
                self.pixel_canvas.pixel_size)
            if axis_hit is not None:
                self._symmetry_axis_dragging = axis_hit
                return

        # If in rotation mode, handle rotation interactions
        if self._rotation_mode:
            self._rotation_handle_click(x, y, event_state)
            return

        # If in selection transform mode, handle transform interactions
        if self._selection_transform is not None:
            self._transform_handle_click(x, y, event_state)
            return

        # If in pasting mode, commit the paste on click
        if self._pasting:
            self._commit_paste()
            return

        # Plugin tool dispatch
        if self.current_tool_name in self.api._plugin_tools:
            self._push_undo()
            self.api._plugin_tools[self.current_tool_name].on_click(self.api, x, y)
            self._render_canvas()
            return

        # Check if active layer is locked
        frame_obj = self.timeline.current_frame_obj()
        if frame_obj.active_layer.locked and self.current_tool_name in (
                "Pen", "Eraser", "Blur", "Fill", "Line", "Rect", "Ellipse", "Polygon", "Roundrect", "Text"):
            self._update_status("Layer is locked")
            return

        # --- TilemapLayer tile-mode drawing ---
        active_layer = frame_obj.active_layer
        if (hasattr(active_layer, 'is_tilemap') and active_layer.is_tilemap()
                and active_layer.edit_mode == "tiles"):
            self._on_tilemap_click(active_layer, x, y)
            return

        layer_grid = self.timeline.current_layer()
        color = self.palette.selected_color
        tool_name = self.current_tool_name

        # Text tool — opens modal dialog
        if tool_name == "Text":
            self._enter_text_mode(x, y)
            return

        # Detect modifier keys from event state bitmask
        shift_held = bool(event_state & 0x0001)
        ctrl_held = bool(event_state & 0x0004)

        size = self._tool_size
        if self._tiled_mode != "off" and tool_name in ("Pen", "Eraser", "Fill", "Blur"):
            x, y = self._wrap_coord(x, y)
        if tool_name in ("Pen", "Eraser", "Blur", "Fill"):
            self._push_undo()
        if tool_name == "Pen":
            self._pp_last_points = [(x, y)]
            self._apply_symmetry_draw(
                lambda px, py: (
                    self._tools["Pen"].apply(
                        layer_grid, px, py, color, size=size,
                        dither_pattern=self._dither_pattern,
                        mask=self._custom_brush_mask)
                    if self._check_ink_mode(layer_grid, px, py) else None),
                x, y)
        elif tool_name == "Eraser":
            self._apply_symmetry_draw(
                lambda px, py: (
                    self._tools["Eraser"].apply(
                        layer_grid, px, py, size=size,
                        mask=self._custom_brush_mask)
                    if self._check_ink_mode(layer_grid, px, py) else None),
                x, y)
        elif tool_name == "Blur":
            self._apply_symmetry_draw(
                lambda px, py: self._tools["Blur"].apply(
                    layer_grid, px, py, size=max(size, 3)),
                x, y)
        elif tool_name == "Fill":
            self._tools["Fill"].apply(layer_grid, x, y, color,
                                      contour=(self._fill_mode == "contour"))
        elif tool_name == "Pick":
            flat_grid = self.timeline.current_frame()
            picked = flat_grid.get_pixel(x, y)
            if picked and picked[3] > 0:
                self.palette.add_color(picked)
                self.palette.select(self.palette.colors.index(picked))
                self.right_panel.palette_panel.refresh()
        elif tool_name == "Line":
            self._line_start = (x, y)
        elif tool_name == "Rect":
            self._rect_start = (x, y)
        elif tool_name == "Roundrect":
            self._roundrect_start = (x, y)
        elif tool_name == "Ellipse":
            self._ellipse_start = (x, y)
        elif tool_name == "Wand":
            wand = self._tools["Wand"]
            grid = self.timeline.current_frame()
            new_pixels = wand.apply(grid, x, y, tolerance=self._wand_tolerance)
            if new_pixels:
                self._selection_pixels = self._apply_selection_op(new_pixels, event_state)
                self.pixel_canvas.draw_wand_selection(self._selection_pixels)
            else:
                if not (event_state & 0x1) and not (event_state & 0x4):
                    self._selection_pixels = None
                    self.pixel_canvas.clear_selection()
        elif tool_name == "Lasso":
            self._lasso_points = [(x, y)]
            shift_held = event_state & 0x1
            ctrl_held = event_state & 0x4
            if not shift_held and not ctrl_held:
                self._selection_pixels = None
                self.pixel_canvas.clear_selection()
        elif tool_name == "Select":
            self._select_start = (x, y)
            shift_held = event_state & 0x1
            ctrl_held = event_state & 0x4
            if not shift_held and not ctrl_held:
                self._selection_pixels = None
                self.pixel_canvas.clear_selection()
        elif tool_name == "Polygon":
            if self._polygon_closing:
                return
            if not self._polygon_points:
                self._push_undo()
            self._polygon_points.append((x, y))
        elif tool_name == "Move":
            if self._selection_pixels:
                self._copy_selection()
                self._delete_selection()
                self._paste_clipboard()
            else:
                self._push_undo()
                self._move_start = (x, y)
                self._move_snapshot = self.timeline.current_layer().copy()

        self._render_canvas()
        self._draw_tool_cursor(x, y)

    def _on_canvas_drag(self, x, y, event_state=0):
        # Reference image drag
        if self._ref_dragging:
            self._ref_update_drag(x, y)
            return

        if self._symmetry_axis_dragging is not None:
            if self._symmetry_axis_dragging == "x":
                self._symmetry_axis_x = max(0, min(self.timeline.width, x))
            else:
                self._symmetry_axis_y = max(0, min(self.timeline.height, y))
            self._draw_symmetry_axis_overlay()
            return

        # If in rotation mode, handle rotation drag
        if self._rotation_mode:
            self._rotation_handle_drag(x, y)
            return

        if self._selection_transform is not None:
            self._transform_handle_drag(x, y, event_state)
            return

        # Plugin tool dispatch
        if self.current_tool_name in self.api._plugin_tools:
            self.api._plugin_tools[self.current_tool_name].on_drag(self.api, x, y)
            self._render_canvas()
            return

        # Check if active layer is locked
        frame_obj = self.timeline.current_frame_obj()
        if frame_obj.active_layer.locked and self.current_tool_name in (
                "Pen", "Eraser", "Blur"):
            return

        # --- TilemapLayer tile-mode drag (Pen/Eraser continue placing tiles) ---
        active_layer = frame_obj.active_layer
        if (hasattr(active_layer, 'is_tilemap') and active_layer.is_tilemap()
                and active_layer.edit_mode == "tiles"):
            if self.current_tool_name in ("Pen", "Eraser"):
                self._on_tilemap_click(active_layer, x, y)
            return

        if self._tiled_mode != "off" and self.current_tool_name in ("Pen", "Eraser", "Blur"):
            x, y = self._wrap_coord(x, y)

        layer_grid = self.timeline.current_layer()
        color = self.palette.selected_color
        size = self._tool_size

        if self.current_tool_name == "Pen":
            # Pixel-perfect mode: remove L-shape corners
            if self._pixel_perfect and size == 1:
                self._pp_last_points.append((x, y))
                if len(self._pp_last_points) >= 3:
                    p0 = self._pp_last_points[-3]
                    p1 = self._pp_last_points[-2]
                    p2 = self._pp_last_points[-1]
                    dx01 = p1[0] - p0[0]
                    dy01 = p1[1] - p0[1]
                    dx12 = p2[0] - p1[0]
                    dy12 = p2[1] - p1[1]
                    is_l = ((dx01 != dx12 or dy01 != dy12) and
                            abs(dx01) <= 1 and abs(dy01) <= 1 and
                            abs(dx12) <= 1 and abs(dy12) <= 1)
                    if is_l:
                        # Erase middle point
                        layer_grid.set_pixel(p1[0], p1[1], (0, 0, 0, 0))
                        self._pp_last_points.pop(-2)
            self._apply_symmetry_draw(
                lambda px, py: (
                    self._tools["Pen"].apply(
                        layer_grid, px, py, color, size=size,
                        dither_pattern=self._dither_pattern,
                        mask=self._custom_brush_mask)
                    if self._check_ink_mode(layer_grid, px, py) else None),
                x, y)
            self._render_canvas()
            self._draw_tool_cursor(x, y)
        elif self.current_tool_name == "Eraser":
            self._apply_symmetry_draw(
                lambda px, py: (
                    self._tools["Eraser"].apply(
                        layer_grid, px, py, size=size,
                        mask=self._custom_brush_mask)
                    if self._check_ink_mode(layer_grid, px, py) else None),
                x, y)
            self._render_canvas()
            self._draw_tool_cursor(x, y)
        elif self.current_tool_name == "Blur":
            self._apply_symmetry_draw(
                lambda px, py: self._tools["Blur"].apply(
                    layer_grid, px, py, size=max(size, 3)),
                x, y)
            self._render_canvas()
            self._draw_tool_cursor(x, y)
        elif self.current_tool_name == "Line" and self._line_start:
            self._render_canvas()
            sx, sy = self._line_start
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            self.pixel_canvas.clear_overlays()
            self.pixel_canvas.draw_line_preview(sx, sy, x, y, hex_color)
        elif self.current_tool_name == "Rect" and self._rect_start:
            self._render_canvas()
            sx, sy = self._rect_start
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            self.pixel_canvas.clear_overlays()
            self.pixel_canvas.draw_rect_preview(sx, sy, x, y, hex_color)
        elif self.current_tool_name == "Roundrect" and self._roundrect_start:
            self._render_canvas()
            sx, sy = self._roundrect_start
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            self.pixel_canvas.clear_overlays()
            self.pixel_canvas.draw_rect_preview(sx, sy, x, y, hex_color)
        elif self.current_tool_name == "Ellipse" and self._ellipse_start:
            self._render_canvas()
            sx, sy = self._ellipse_start
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            self.pixel_canvas.clear_overlays()
            self.pixel_canvas.draw_rect_preview(sx, sy, x, y, hex_color)
        elif self.current_tool_name == "Lasso" and self._lasso_points:
            self._lasso_points.append((x, y))
            self.pixel_canvas.draw_lasso_preview(self._lasso_points)
        elif self.current_tool_name == "Select" and self._select_start:
            sx, sy = self._select_start
            self.pixel_canvas.clear_overlays()
            self.pixel_canvas.clear_selection()
            self.pixel_canvas.draw_selection(sx, sy, x, y)
        elif self.current_tool_name == "Move" and self._move_start:
            ctrl_snap = bool(event_state & 0x0004) and self._grid_settings.custom_grid_visible
            mx, my = self._grid_settings.snap(x, y) if ctrl_snap else (x, y)
            dx = mx - self._move_start[0]
            dy = my - self._move_start[1]
            shifted = _shift_grid(self._move_snapshot, dx, dy)
            layer = self.timeline.current_layer()
            layer._pixels = shifted._pixels.copy()
            self._render_canvas()
            self._update_status(f"Move: ({dx}, {dy})")

    def _on_canvas_release(self, x, y, event_state=0):
        if self._ref_dragging:
            self._ref_end_drag()
            return

        if self._symmetry_axis_dragging is not None:
            self._symmetry_axis_dragging = None
            return

        if self._rotation_mode:
            self._rotation_handle_release(x, y, event_state)
            return

        if self._selection_transform is not None:
            self._transform_handle_release(x, y, event_state)
            return

        # Plugin tool dispatch
        if self.current_tool_name in self.api._plugin_tools:
            self.api._plugin_tools[self.current_tool_name].on_release(self.api, x, y)
            self._render_canvas()
            return

        # --- TilemapLayer tile-mode: no special release action ---
        frame_obj_r = self.timeline.current_frame_obj()
        active_layer_r = frame_obj_r.active_layer
        if (hasattr(active_layer_r, 'is_tilemap') and active_layer_r.is_tilemap()
                and active_layer_r.edit_mode == "tiles"):
            self._pp_last_points = []
            self._render_canvas()
            self.timeline_panel.refresh()
            return

        # --- TilemapLayer pixel-auto-mode: sync tiles after stroke ---
        if (hasattr(active_layer_r, 'is_tilemap') and active_layer_r.is_tilemap()
                and active_layer_r.edit_mode == "pixels"
                and active_layer_r.pixel_sub_mode == "auto"):
            self._tilemap_auto_sync(active_layer_r)

        layer_grid = self.timeline.current_layer()
        color = self.palette.selected_color

        if self._tiled_mode != "off":
            x, y = self._wrap_coord(x, y)

        if self.current_tool_name == "Line" and self._line_start:
            self._push_undo()
            sx, sy = self._line_start
            self._tools["Line"].apply(layer_grid, sx, sy, x, y, color, width=self._tool_size)
            self._line_start = None
            self.pixel_canvas.clear_overlays()
        elif self.current_tool_name == "Rect" and self._rect_start:
            self._push_undo()
            sx, sy = self._rect_start
            self._tools["Rect"].apply(layer_grid, sx, sy, x, y, color, filled=False, width=self._tool_size)
            self._rect_start = None
            self.pixel_canvas.clear_overlays()
        elif self.current_tool_name == "Roundrect" and self._roundrect_start:
            self._push_undo()
            sx, sy = self._roundrect_start
            self._tools["RoundedRect"].apply(layer_grid, sx, sy, x, y, color,
                                             radius=self._corner_radius, filled=False,
                                             width=self._tool_size)
            self._roundrect_start = None
            self.pixel_canvas.clear_overlays()
        elif self.current_tool_name == "Ellipse" and self._ellipse_start:
            self._push_undo()
            sx, sy = self._ellipse_start
            self._tools["Ellipse"].apply(layer_grid, sx, sy, x, y, color, filled=False, width=self._tool_size)
            self._ellipse_start = None
            self.pixel_canvas.clear_overlays()
        elif self.current_tool_name == "Lasso" and self._lasso_points:
            self._lasso_points.append((x, y))
            lasso = self._tools["Lasso"]
            w, h = self.timeline.width, self.timeline.height
            new_pixels = lasso.fill_interior(self._lasso_points, w, h)
            if new_pixels:
                self._selection_pixels = self._apply_selection_op(new_pixels, event_state)
                self.pixel_canvas.draw_wand_selection(self._selection_pixels)
            self._lasso_points = []
            self.pixel_canvas.clear_overlays()
        elif self.current_tool_name == "Select" and self._select_start:
            sx, sy = self._select_start
            x0, y0 = min(sx, x), min(sy, y)
            x1, y1 = max(sx, x), max(sy, y)
            w, h = self.timeline.width, self.timeline.height
            new_pixels = {(px, py) for px in range(max(0, x0), min(w, x1 + 1))
                          for py in range(max(0, y0), min(h, y1 + 1))}
            self._selection_pixels = self._apply_selection_op(new_pixels, event_state)
            self._select_start = None
            self.pixel_canvas.draw_wand_selection(self._selection_pixels)
        elif self.current_tool_name == "Move" and self._move_start:
            self._move_start = None
            self._move_snapshot = None
            self._render_canvas()

        self._pp_last_points = []
        self._render_canvas()
        self.timeline_panel.refresh()

    def _draw_tool_cursor(self, x, y):
        """Draw the cursor highlight for the current tool at (x, y)."""
        self.pixel_canvas.clear_overlays()
        tool = self.current_tool_name
        size = self._tool_size

        if tool in ("Pen", "Fill", "Pick", "Ellipse", "Rect"):
            color = self.palette.selected_color
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            s = size if tool == "Pen" else 1
            self.pixel_canvas.draw_cursor_highlight(x, y, hex_color, size=s)
        elif tool == "Eraser":
            self.pixel_canvas.draw_cursor_highlight(x, y, "#ff4444", size=size)
        elif tool == "Blur":
            self.pixel_canvas.draw_cursor_highlight(x, y, "#88aaff",
                                                    size=max(size, 3))
        elif tool in ("Select", "Wand"):
            self.pixel_canvas.draw_cursor_highlight(x, y, "#00bfff")

    def _on_canvas_motion(self, x, y):
        """Handle mouse hover — show cursor highlight and tool previews."""
        self._last_cursor_pos = (x, y)
        # Symmetry axis cursor feedback
        if self._symmetry_mode != "off" and not self._text_mode:
            axis_hit = _hit_test_symmetry_axis(
                x, y, self._symmetry_mode,
                self._symmetry_axis_x, self._symmetry_axis_y,
                self.pixel_canvas.pixel_size)
            if axis_hit == "x":
                self.pixel_canvas.config(cursor="sb_h_double_arrow")
            elif axis_hit == "y":
                self.pixel_canvas.config(cursor="sb_v_double_arrow")
        # Transform mode cursor feedback
        if self._selection_transform is not None:
            from src.selection_transform import hit_test_transform_handle
            hit = hit_test_transform_handle(
                self._selection_transform, x, y, self.pixel_canvas.pixel_size)
            cursors = {
                "inside": "fleur", "outside": "exchange", "pivot": "crosshair",
            }
            if hit and hit.startswith("corner:"):
                self.pixel_canvas.config(cursor="sizing")
            elif hit and hit.startswith("midpoint:"):
                if "top" in hit or "bottom" in hit:
                    self.pixel_canvas.config(cursor="sb_v_double_arrow")
                else:
                    self.pixel_canvas.config(cursor="sb_h_double_arrow")
            elif hit in cursors:
                self.pixel_canvas.config(cursor=cursors[hit])
            else:
                self.pixel_canvas.config(cursor="arrow")
            return
        # Floating paste follows the cursor
        if self._pasting and self._clipboard:
            self._paste_pos = (x, y)
            self.pixel_canvas.draw_floating_pixels(self._clipboard, x, y)
            return

        # Tile cursor preview in "tiles" edit mode
        frame_obj_m = self.timeline.current_frame_obj()
        active_layer_m = frame_obj_m.active_layer
        if (hasattr(active_layer_m, 'is_tilemap') and active_layer_m.is_tilemap()
                and active_layer_m.edit_mode == "tiles"):
            self._draw_tile_cursor_preview(active_layer_m, x, y)
            return

        # Polygon preview: show edges so far + line to cursor
        if self.current_tool_name == "Polygon" and self._polygon_points:
            self.pixel_canvas.clear_overlays()
            color = self.palette.selected_color
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            for i in range(len(self._polygon_points) - 1):
                sx, sy = self._polygon_points[i]
                ex, ey = self._polygon_points[i + 1]
                self.pixel_canvas.draw_line_preview(sx, sy, ex, ey, hex_color)
            # Line from last vertex to cursor
            lx, ly = self._polygon_points[-1]
            self.pixel_canvas.draw_line_preview(lx, ly, x, y, hex_color)
            return

        self._draw_tool_cursor(x, y)

    def _on_canvas_double_click(self, event):
        """Close and commit the polygon on double-click."""
        if self.current_tool_name == "Polygon" and len(self._polygon_points) >= 3:
            self._commit_polygon()

    def _on_canvas_right_click(self, x, y):
        """Handle right-click on canvas — tile pick or symmetry axis popup."""
        # Tilemap tile picking: right-click in tile mode picks the tile
        frame_obj = self.timeline.current_frame_obj()
        layer = frame_obj.active_layer
        if (hasattr(layer, 'is_tilemap') and layer.is_tilemap()
                and layer.edit_mode == "tiles"):
            tw = layer.tileset.tile_width
            th = layer.tileset.tile_height
            col = x // tw
            row = y // th
            if 0 <= row < layer.grid_rows and 0 <= col < layer.grid_cols:
                ref = layer.grid[row][col]
                tp = self.right_panel.tiles_panel
                if tp is not None:
                    tp.selected_tile_index = ref.index
                    tp.flip_x = ref.flip_x
                    tp.flip_y = ref.flip_y
                    tp.refresh()
                    name = f"tile #{ref.index}" if ref.index > 0 else "empty tile"
                    self._update_status(f"Picked {name}")
                    self._draw_tilemap_highlight(layer)
            return

        # Symmetry axis popup
        if self._symmetry_mode != "off":
            axis_hit = _hit_test_symmetry_axis(
                x, y, self._symmetry_mode,
                self._symmetry_axis_x, self._symmetry_axis_y,
                self.pixel_canvas.pixel_size)
            if axis_hit is not None:
                self._show_axis_position_popup(axis_hit)

    def _show_axis_position_popup(self, axis: str):
        """Show a small popup for precise axis positioning."""
        from src.ui.theme import (
            ACCENT_CYAN, BG_DEEP, BG_PANEL_ALT,
            BUTTON_BG, BUTTON_HOVER, TEXT_PRIMARY, TEXT_SECONDARY,
        )

        popup = tk.Toplevel(self.root)
        popup.title("Axis Position")
        popup.configure(bg=BG_DEEP)
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()

        font = ("Consolas", 9)
        x_var = None
        y_var = None

        if axis == "x" or self._symmetry_mode == "both":
            row_x = tk.Frame(popup, bg=BG_DEEP)
            row_x.pack(fill="x", padx=10, pady=(10, 2))
            tk.Label(row_x, text="X:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                     font=font).pack(side="left")
            x_var = tk.IntVar(value=self._symmetry_axis_x)
            tk.Spinbox(row_x, from_=0, to=self.timeline.width, width=5,
                       textvariable=x_var, font=font,
                       bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                       buttonbackground=BUTTON_BG).pack(side="left", padx=4)

        if axis == "y" or self._symmetry_mode == "both":
            row_y = tk.Frame(popup, bg=BG_DEEP)
            row_y.pack(fill="x", padx=10, pady=2)
            tk.Label(row_y, text="Y:", bg=BG_DEEP, fg=TEXT_PRIMARY,
                     font=font).pack(side="left")
            y_var = tk.IntVar(value=self._symmetry_axis_y)
            tk.Spinbox(row_y, from_=0, to=self.timeline.height, width=5,
                       textvariable=y_var, font=font,
                       bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                       buttonbackground=BUTTON_BG).pack(side="left", padx=4)

        btn_row = tk.Frame(popup, bg=BG_DEEP)
        btn_row.pack(fill="x", padx=10, pady=(6, 10))

        def _apply():
            if x_var is not None:
                self._symmetry_axis_x = x_var.get()
            if y_var is not None:
                self._symmetry_axis_y = y_var.get()
            popup.destroy()
            self._draw_symmetry_axis_overlay()

        tk.Button(btn_row, text="OK", bg=ACCENT_CYAN, fg=BG_DEEP,
                  font=("Consolas", 9, "bold"), relief="flat", padx=12,
                  command=_apply).pack(side="right", padx=4)
        tk.Button(btn_row, text="Cancel", bg=BUTTON_BG, fg=TEXT_PRIMARY,
                  font=font, relief="flat", padx=12,
                  command=popup.destroy).pack(side="right", padx=4)

        popup.update_idletasks()
        pw, ph = self.root.winfo_width(), self.root.winfo_height()
        px, py = self.root.winfo_rootx(), self.root.winfo_rooty()
        w, h = popup.winfo_width(), popup.winfo_height()
        popup.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _on_escape(self):
        """Escape cancels transform/rotation/paste mode first, then clears selection."""
        if self._selection_transform is not None:
            self._cancel_selection_transform()
        elif self._rotation_mode:
            self._exit_rotation_mode(apply=False)
        elif self._pasting:
            self._cancel_paste()
        elif self._polygon_points:
            self._cancel_polygon()
        else:
            self._clear_selection()

    def _on_enter_key(self):
        """Enter applies transform/rotation if in mode."""
        if self._selection_transform is not None:
            self._commit_selection_transform()
        elif self._rotation_mode:
            self._exit_rotation_mode(apply=True)
        elif self._polygon_points:
            self._commit_polygon()

    def _on_f_key(self):
        """F key: fill selection with current color, or switch to Fill tool."""
        if self._selection_pixels:
            self._fill_selection()
        else:
            self.toolbar.select_tool("Fill")

    def _commit_polygon(self):
        """Finalize the polygon: draw it onto the layer and reset state."""
        if len(self._polygon_points) < 2:
            self._polygon_points = []
            return
        self._polygon_closing = True
        layer_grid = self.timeline.current_layer()
        color = self.palette.selected_color
        size = self._tool_size
        self._tools["Polygon"].apply(
            layer_grid, self._polygon_points, color,
            filled=False, width=size)
        self._polygon_points = []
        self._polygon_closing = False
        self.pixel_canvas.clear_overlays()
        self._render_canvas()
        self.timeline_panel.refresh()

    def _cancel_polygon(self):
        """Cancel polygon drawing — pop undo to restore canvas."""
        self._polygon_points = []
        self._polygon_closing = False
        self._undo()
        self.pixel_canvas.clear_overlays()
        self._render_canvas()

    def _apply_selection_op(self, new_pixels, event_state=0):
        """Apply selection operation based on modifier keys."""
        shift_held = event_state & 0x1
        ctrl_held = event_state & 0x4
        existing = self._selection_pixels or set()
        if shift_held and ctrl_held:
            return existing & new_pixels      # Intersect
        elif shift_held:
            return existing | new_pixels      # Add
        elif ctrl_held:
            return existing - new_pixels      # Subtract
        else:
            return new_pixels                 # Replace

    def _clear_selection(self):
        """Clear the active selection."""
        self._selection_pixels = None
        self._select_start = None
        self.pixel_canvas.clear_selection()
        self.pixel_canvas.clear_overlays()

    def _fill_selection(self):
        """Fill selection pixels with current color."""
        if not self._selection_pixels:
            return
        self._push_undo()
        color = self.palette.selected_color
        layer = self.timeline.current_layer()
        for (px, py) in self._selection_pixels:
            layer.set_pixel(px, py, color)
        self._render_canvas()

    def _delete_selection(self):
        """Clear selection pixels to transparent."""
        if self._selection_pixels:
            self._push_undo()
            layer = self.timeline.current_layer()
            for (px, py) in self._selection_pixels:
                layer.set_pixel(px, py, (0, 0, 0, 0))
            self._render_canvas()
        elif self.timeline.frame_count > 1:
            self._delete_frame()

    def _capture_brush(self):
        """Capture selected pixels as a custom brush shape."""
        if not self._selection_pixels:
            return
        # Compute center of selection
        xs = [p[0] for p in self._selection_pixels]
        ys = [p[1] for p in self._selection_pixels]
        cx = (min(xs) + max(xs)) // 2
        cy = (min(ys) + max(ys)) // 2
        # Store as relative offsets from center
        grid = self.timeline.current_frame()
        mask = set()
        for (px, py) in self._selection_pixels:
            color = grid.get_pixel(px, py)
            if color[3] > 0:  # only include non-transparent pixels
                mask.add((px - cx, py - cy))
        if mask:
            self._custom_brush_mask = mask
            self._update_status(f"Custom brush: {len(mask)} pixels")
        self._clear_selection()

    def _reset_brush(self):
        """Reset to default square brush."""
        self._custom_brush_mask = None
        self._update_status("Brush reset to default")

    def _copy_selection(self):
        """Copy selected pixels to clipboard."""
        if not self._selection_pixels:
            return
        xs = [p[0] for p in self._selection_pixels]
        ys = [p[1] for p in self._selection_pixels]
        x0, y0 = min(xs), min(ys)
        x1, y1 = max(xs), max(ys)
        w = x1 - x0 + 1
        h = y1 - y0 + 1
        grid = self.timeline.current_frame()
        clip = PixelGrid(w, h)
        for (px, py) in self._selection_pixels:
            color = grid.get_pixel(px, py)
            clip.set_pixel(px - x0, py - y0, color)
        self._clipboard = clip
        self._paste_origin = (x0, y0)

    def _paste_clipboard(self):
        """Enter floating paste mode with transform handles."""
        if self._clipboard is None:
            return
        from src.selection_transform import SelectionTransform

        self._pasting = False
        self._clear_selection()
        img = self._clipboard.to_pil_image()
        origin = self._grid_settings.snap(*self._paste_origin)
        self._selection_transform = SelectionTransform(
            pixels=img,
            position=origin,
            source="paste",
        )
        self._draw_transform_overlay()
        self._show_transform_context_bar()
        self._update_status("Transform: drag handles, Enter=apply, Esc=cancel")

    def _commit_paste(self):
        """Commit the floating paste to the canvas."""
        if not self._pasting or not self._clipboard:
            return
        self._push_undo()
        grid = self.timeline.current_layer()
        px, py = self._paste_pos
        grid.paste_region(self._clipboard, px, py)
        self._pasting = False
        self.pixel_canvas.clear_floating()
        self._render_canvas()
        self._update_status("Pasted")

    def _cancel_paste(self):
        """Cancel the floating paste without committing."""
        self._pasting = False
        self.pixel_canvas.clear_floating()
        self._update_status()

    def _wrap_coord(self, x, y):
        """Wrap coordinates based on tiled mode. Returns (x, y)."""
        w, h = self.timeline.width, self.timeline.height
        mode = self._tiled_mode
        if mode in ("x", "both"):
            x = x % w
        if mode in ("y", "both"):
            y = y % h
        return x, y

    def _apply_symmetry_draw(self, fn, x, y):
        """Apply a draw function with symmetry mirroring."""
        fn(x, y)
        cx = self._symmetry_axis_x
        cy = self._symmetry_axis_y
        if self._symmetry_mode in ("horizontal", "both"):
            fn(2 * cx - x - 1, y)
        if self._symmetry_mode in ("vertical", "both"):
            fn(x, 2 * cy - y - 1)
        if self._symmetry_mode == "both":
            fn(2 * cx - x - 1, 2 * cy - y - 1)

    def _shade_at_cursor(self, mode: str):
        """Apply shading ink (lighten/darken) at last known cursor position."""
        layer_grid = self.timeline.current_layer()
        palette_colors = [c for c in self.palette.colors if c[3] > 0]
        if not palette_colors:
            return
        # Apply on the entire canvas where there are non-transparent pixels
        # For simplicity, we use a "temporary tool" approach: shade under cursor
        # We need a way to know cursor position. Use a simple approach:
        # shade is applied via keyboard at last drawn position
        # For now, store last cursor position from motion
        if hasattr(self, '_last_cursor_pos'):
            x, y = self._last_cursor_pos
            self._push_undo()
            self._tools["ShadingInk"].apply(
                layer_grid, x, y, palette_colors, mode=mode)
            self._render_canvas()
            self._update_status(f"Shade: {mode}")

    def _check_ink_mode(self, grid, x, y):
        """Check if the ink mode allows painting at (x, y).
        Returns True if painting is allowed."""
        if self._ink_mode == "normal":
            return True
        current = grid.get_pixel(x, y)
        if current is None:
            return self._ink_mode == "behind"
        alpha = current[3]
        if self._ink_mode == "alpha_lock":
            return alpha > 0
        if self._ink_mode == "behind":
            return alpha == 0
        return True

    # --- Reference image drag ---

    def _ref_begin_drag(self, x, y):
        """Start dragging the reference image."""
        self._ref_dragging = True
        self._ref_drag_start = (x, y)
        self._ref_drag_origin = (self._reference.x, self._reference.y)

    def _ref_update_drag(self, x, y):
        """Update reference position during drag."""
        if self._ref_drag_start is None:
            return
        dx = x - self._ref_drag_start[0]
        dy = y - self._ref_drag_start[1]
        self._reference.x = self._ref_drag_origin[0] + dx
        self._reference.y = self._ref_drag_origin[1] + dy
        self._render_canvas()

    def _ref_end_drag(self):
        """End reference image drag."""
        self._ref_dragging = False
        self._ref_drag_start = None
        self._ref_drag_origin = None

    def _ref_adjust_scale(self, delta, mx, my):
        """Adjust reference image scale, anchoring around (mx, my)."""
        ref = self._reference
        if ref is None:
            return
        old_scale = ref.scale
        new_scale = max(0.1, min(10.0, old_scale + delta))
        if new_scale == old_scale:
            return
        # Anchor around mouse position: adjust x, y so pixel under cursor stays
        ratio = new_scale / old_scale
        ref.x = int(mx - (mx - ref.x) * ratio)
        ref.y = int(my - (my - ref.y) * ratio)
        ref.scale = new_scale
        self._render_canvas()

    def _on_ref_scroll(self, event):
        """Ctrl+Alt+scroll: resize reference image."""
        if self._reference is None:
            return
        delta = 0.1 if event.delta > 0 else -0.1
        # Convert screen coords to canvas pixel coords
        x, y = self.pixel_canvas._to_grid_coords(event)
        self._ref_adjust_scale(delta, x, y)

    # --- Selection transform mode ---

    def _enter_selection_transform(self):
        """Enter selection transform mode via Ctrl+T."""
        from src.selection_transform import SelectionTransform

        if self._selection_transform is not None:
            return

        if self._pasting and self._clipboard:
            img = self._clipboard.to_pil_image()
            self._selection_transform = SelectionTransform(
                pixels=img,
                position=self._paste_pos,
                source="paste",
            )
            self._pasting = False
            self.pixel_canvas.clear_floating()
            self._draw_transform_overlay()
            self._show_transform_context_bar()
            self._update_status("Transform: drag handles, Enter=apply, Esc=cancel")
            return

        if self._selection_pixels and len(self._selection_pixels) > 0:
            self._push_undo()
            xs = [p[0] for p in self._selection_pixels]
            ys = [p[1] for p in self._selection_pixels]
            x0, y0 = min(xs), min(ys)
            x1, y1 = max(xs), max(ys)
            w, h = x1 - x0 + 1, y1 - y0 + 1

            grid = self.timeline.current_layer()
            clip = PixelGrid(w, h)
            for (px, py) in self._selection_pixels:
                color = grid.get_pixel(px, py)
                clip.set_pixel(px - x0, py - y0, color)
                grid.set_pixel(px, py, (0, 0, 0, 0))

            img = clip.to_pil_image()
            self._selection_transform = SelectionTransform(
                pixels=img,
                position=(x0, y0),
                source="float",
            )
            self._clear_selection()
            self._render_canvas()
            self._draw_transform_overlay()
            self._show_transform_context_bar()
            self._update_status("Transform: drag handles, Enter=apply, Esc=cancel")
            return

        # No selection or paste — float the entire layer content
        layer_grid = self.timeline.current_layer()
        pixels = layer_grid._pixels
        if pixels[:, :, 3].max() == 0:
            self._update_status("Nothing to transform")
            return

        # Find bounding box of non-transparent pixels
        mask = pixels[:, :, 3] > 0
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        if not rows.any():
            self._update_status("Nothing to transform")
            return
        y0 = int(np.argmax(rows))
        y1 = int(len(rows) - np.argmax(rows[::-1]))
        x0 = int(np.argmax(cols))
        x1 = int(len(cols) - np.argmax(cols[::-1]))
        w, h = x1 - x0, y1 - y0

        self._push_undo()
        clip = PixelGrid(w, h)
        clip._pixels[:] = pixels[y0:y1, x0:x1]
        # Clear the floated pixels from the layer
        pixels[y0:y1, x0:x1] = 0

        img = clip.to_pil_image()
        self._selection_transform = SelectionTransform(
            pixels=img,
            position=(x0, y0),
            source="float",
        )
        self._render_canvas()
        self._draw_transform_overlay()
        self._show_transform_context_bar()
        self._update_status("Transform: drag handles, Enter=apply, Esc=cancel")

    def _draw_transform_overlay(self):
        """Render the transform preview and handles on the canvas."""
        from src.selection_transform import (
            compute_affine_preview, get_transform_bounding_box,
        )
        t = self._selection_transform
        if t is None:
            return

        preview = compute_affine_preview(t)
        preview_grid = PixelGrid.from_pil_image(preview)

        corners = get_transform_bounding_box(t)
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        draw_x = int(min(xs))
        draw_y = int(min(ys))

        self.pixel_canvas.draw_floating_pixels(preview_grid, draw_x, draw_y)
        self.pixel_canvas.draw_transform_handles(
            corners, t.pivot, t.position, self.pixel_canvas.pixel_size)

    def _commit_selection_transform(self):
        """Apply the transform and paste onto the active layer."""
        from src.selection_transform import (
            compute_affine_final, get_transform_bounding_box, clip_to_canvas,
        )
        t = self._selection_transform
        if t is None:
            return

        self._push_undo()
        final_img = compute_affine_final(t)

        corners = get_transform_bounding_box(t)
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        place_x = int(min(xs))
        place_y = int(min(ys))

        grid = self.timeline.current_layer()
        clip_to_canvas(final_img, (place_x, place_y), grid)

        self._selection_transform = None
        self.pixel_canvas.clear_floating()
        self.pixel_canvas.clear_transform_handles()
        self._hide_transform_context_bar()
        self.pixel_canvas.config(cursor="arrow")
        self._render_canvas()
        self._update_status("Transform applied")

    def _cancel_selection_transform(self):
        """Cancel the transform, restoring original pixels if floated."""
        t = self._selection_transform
        if t is None:
            return

        self._selection_transform = None
        self.pixel_canvas.clear_floating()
        self.pixel_canvas.clear_transform_handles()
        self._hide_transform_context_bar()
        self.pixel_canvas.config(cursor="arrow")

        if t.source == "float":
            # Undo the float (restores the pre-cut layer state)
            self._undo()
        else:
            self._render_canvas()
        self._update_status("Transform cancelled")

    # --- Task 8: Transform drag handlers ---

    def _transform_handle_click(self, x, y, event_state=0):
        """Handle mouse click during selection transform mode."""
        from src.selection_transform import hit_test_transform_handle, SelectionTransform

        t = self._selection_transform
        hit = hit_test_transform_handle(t, x, y, self.pixel_canvas.pixel_size)

        self._transform_drag_zone = hit
        self._transform_drag_start = (x, y)
        self._transform_start_state = {
            "position": t.position,
            "rotation": t.rotation,
            "scale_x": t.scale_x,
            "scale_y": t.scale_y,
            "skew_x": t.skew_x,
            "skew_y": t.skew_y,
            "pivot": t.pivot,
        }
        self._transform_ctrl_held = bool(event_state & 0x0004)
        self._transform_shift_held = bool(event_state & 0x0001)

        if hit == "outside":
            pvx = t.position[0] + t.pivot[0]
            pvy = t.position[1] + t.pivot[1]
            self._transform_mouse_start_angle = math.degrees(
                math.atan2(y - pvy, x - pvx))

        # Set cursor
        cursors = {
            "inside": "fleur",
            "outside": "exchange",
            "pivot": "crosshair",
        }
        if hit and hit.startswith("corner:"):
            cursor = "sizing" if not (event_state & 0x0004) else "crosshair"
        elif hit and hit.startswith("midpoint:"):
            if "top" in hit or "bottom" in hit:
                cursor = "sb_v_double_arrow"
            else:
                cursor = "sb_h_double_arrow"
        else:
            cursor = cursors.get(hit, "arrow")
        self.pixel_canvas.config(cursor=cursor)

    def _transform_handle_drag(self, x, y, event_state=0):
        """Handle mouse drag during selection transform mode."""
        from src.selection_transform import SelectionTransform, get_transform_bounding_box

        t = self._selection_transform
        if t is None:
            return
        zone = self._transform_drag_zone
        if zone is None:
            return

        start = self._transform_start_state
        sx, sy = self._transform_drag_start
        dx, dy = x - sx, y - sy
        ctrl_snap = bool(event_state & 0x0004) and self._grid_settings.custom_grid_visible

        if zone == "inside":
            new_pos = (start["position"][0] + dx, start["position"][1] + dy)
            t.position = self._grid_settings.snap(*new_pos) if ctrl_snap else new_pos

        elif zone == "outside":
            pvx = t.position[0] + t.pivot[0]
            pvy = t.position[1] + t.pivot[1]
            current_angle = math.degrees(math.atan2(y - pvy, x - pvx))
            delta = current_angle - self._transform_mouse_start_angle
            new_rot = start["rotation"] + delta
            if self._transform_shift_held:
                new_rot = round(new_rot / 15) * 15
            t.rotation = new_rot

        elif zone == "pivot":
            t.pivot = (start["pivot"][0] + dx, start["pivot"][1] + dy)

        elif zone.startswith("corner:"):
            ctrl_held = bool(self._transform_ctrl_held)
            shift_held = bool(self._transform_shift_held)
            if ctrl_held:
                idx = int(zone.split(":")[1])
                # Top/bottom corners (0,1 / 2,3) → skew X
                # Left/right corners (0,3 / 1,2) → skew Y
                if idx in (0, 1):  # top edge
                    t.skew_x = start["skew_x"] + dx * 0.5
                elif idx in (2, 3):  # bottom edge
                    t.skew_x = start["skew_x"] - dx * 0.5
                if idx in (0, 3):  # left edge
                    t.skew_y = start["skew_y"] + dy * 0.5
                elif idx in (1, 2):  # right edge
                    t.skew_y = start["skew_y"] - dy * 0.5
            else:
                pvx = t.position[0] + t.pivot[0]
                pvy = t.position[1] + t.pivot[1]
                corner_idx = int(zone.split(":")[1])
                orig_corners = get_transform_bounding_box(SelectionTransform(
                    pixels=t.pixels, position=start["position"],
                    rotation=start["rotation"],
                    scale_x=start["scale_x"], scale_y=start["scale_y"],
                    skew_x=start["skew_x"], skew_y=start["skew_y"],
                    pivot=start["pivot"],
                ))
                orig_corner = orig_corners[corner_idx]
                orig_dist = math.hypot(orig_corner[0] - pvx, orig_corner[1] - pvy)
                new_dist = math.hypot(x - pvx, y - pvy)
                if orig_dist > 0.1:
                    factor = new_dist / orig_dist
                    if shift_held:
                        x_dist = abs(x - pvx)
                        y_dist = abs(y - pvy)
                        orig_x_dist = abs(orig_corner[0] - pvx)
                        orig_y_dist = abs(orig_corner[1] - pvy)
                        if orig_x_dist > 0.1:
                            t.scale_x = start["scale_x"] * (x_dist / orig_x_dist)
                        if orig_y_dist > 0.1:
                            t.scale_y = start["scale_y"] * (y_dist / orig_y_dist)
                    else:
                        t.scale_x = start["scale_x"] * factor
                        t.scale_y = start["scale_y"] * factor

        elif zone.startswith("midpoint:"):
            side = zone.split(":")[1]
            pvx = t.position[0] + t.pivot[0]
            pvy = t.position[1] + t.pivot[1]
            w, h = t.pixels.size
            if side in ("left", "right"):
                orig_half = (w / 2.0) * start["scale_x"]
                if orig_half > 0.1:
                    new_half = abs(x - pvx)
                    t.scale_x = start["scale_x"] * (new_half / orig_half)
            else:
                orig_half = (h / 2.0) * start["scale_y"]
                if orig_half > 0.1:
                    new_half = abs(y - pvy)
                    t.scale_y = start["scale_y"] * (new_half / orig_half)

        self._draw_transform_overlay()
        self._update_transform_context_display()

    def _transform_handle_release(self, x, y, event_state=0):
        """Handle mouse release during selection transform mode."""
        t = self._selection_transform
        zone = self._transform_drag_zone

        if zone == "outside" and bool(event_state & 0x0001):
            t.rotation = round(t.rotation / 15) * 15
            self._draw_transform_overlay()
            self._update_transform_context_display()

        self._transform_drag_zone = None
        self.pixel_canvas.config(cursor="arrow")

    # --- Task 9: Transform context bar ---

    def _show_transform_context_bar(self):
        """Show context bar with angle, scale, apply/cancel buttons."""
        self._hide_transform_context_bar()

        from src.ui.theme import (
            ACCENT_CYAN, BG_DEEP, BG_PANEL, BG_PANEL_ALT,
            BUTTON_BG, BUTTON_HOVER, TEXT_PRIMARY, TEXT_SECONDARY,
        )

        frame = tk.Frame(self.options_bar, bg=BG_PANEL)
        frame.pack(side="right", padx=4)
        self._transform_context_frame = frame

        tk.Label(frame, text="Transform", fg=ACCENT_CYAN, bg=BG_PANEL,
                 font=("Consolas", 8, "bold")).pack(side="left", padx=(4, 8))

        tk.Label(frame, text="Angle:", fg=TEXT_SECONDARY, bg=BG_PANEL,
                 font=("Consolas", 8)).pack(side="left", padx=(0, 2))
        self._transform_angle_var = tk.StringVar(value="0.0")
        angle_entry = tk.Entry(frame, textvariable=self._transform_angle_var,
                               width=6, bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                               font=("Consolas", 8), insertbackground=TEXT_PRIMARY)
        angle_entry.pack(side="left", padx=2)
        angle_entry.bind("<Return>", self._on_transform_angle_entry)
        tk.Label(frame, text="\u00b0", fg=TEXT_SECONDARY, bg=BG_PANEL,
                 font=("Consolas", 8)).pack(side="left")

        tk.Label(frame, text="Scale:", fg=TEXT_SECONDARY, bg=BG_PANEL,
                 font=("Consolas", 8)).pack(side="left", padx=(8, 2))
        self._transform_scale_var = tk.StringVar(value="100")
        scale_entry = tk.Entry(frame, textvariable=self._transform_scale_var,
                               width=5, bg=BG_PANEL_ALT, fg=TEXT_PRIMARY,
                               font=("Consolas", 8), insertbackground=TEXT_PRIMARY)
        scale_entry.pack(side="left", padx=2)
        scale_entry.bind("<Return>", self._on_transform_scale_entry)
        tk.Label(frame, text="%", fg=TEXT_SECONDARY, bg=BG_PANEL,
                 font=("Consolas", 8)).pack(side="left")

        tk.Button(frame, text="Apply", bg=ACCENT_CYAN, fg=BG_DEEP,
                  font=("Consolas", 8, "bold"), relief="flat",
                  activebackground=BUTTON_HOVER,
                  command=self._commit_selection_transform
                  ).pack(side="left", padx=(8, 2))

        tk.Button(frame, text="Cancel", bg=BUTTON_BG, fg=TEXT_PRIMARY,
                  font=("Consolas", 8), relief="flat",
                  activebackground=BUTTON_HOVER,
                  command=self._cancel_selection_transform
                  ).pack(side="left", padx=2)

    def _hide_transform_context_bar(self):
        """Remove the transform context bar."""
        frame = getattr(self, '_transform_context_frame', None)
        if frame is not None:
            frame.destroy()
            self._transform_context_frame = None

    def _update_transform_context_display(self):
        """Update angle and scale displays in the context bar."""
        t = self._selection_transform
        if t is None:
            return
        if hasattr(self, '_transform_angle_var'):
            self._transform_angle_var.set(f"{t.rotation:.1f}")
        if hasattr(self, '_transform_scale_var'):
            avg_scale = (t.scale_x + t.scale_y) / 2.0
            self._transform_scale_var.set(f"{avg_scale * 100:.0f}")

    def _on_transform_angle_entry(self, event=None):
        """Handle manual angle entry in context bar."""
        try:
            angle = float(self._transform_angle_var.get())
            self._selection_transform.rotation = angle
            self._draw_transform_overlay()
        except (ValueError, AttributeError):
            pass
        return "break"  # Prevent Enter from committing the transform

    def _on_transform_scale_entry(self, event=None):
        """Handle manual scale entry in context bar."""
        try:
            pct = float(self._transform_scale_var.get())
            factor = pct / 100.0
            if factor > 0:
                self._selection_transform.scale_x = factor
                self._selection_transform.scale_y = factor
                self._draw_transform_overlay()
        except (ValueError, AttributeError):
            pass
        return "break"  # Prevent Enter from committing the transform

    # ------------------------------------------------------------------
    # Text tool methods
    # ------------------------------------------------------------------

    def _enter_text_mode(self, x, y):
        """Open text dialog at canvas position (x, y) with live preview."""
        from src.ui.text_dialog import TextDialog

        self._text_mode = True
        self._text_pos = self._grid_settings.snap(x, y)

        def _preview(settings):
            """Live preview callback — render text on canvas."""
            text = settings.get("text", "")
            if not text.strip():
                self.pixel_canvas.clear_floating()
                return
            color = self.palette.selected_color
            img = self._render_text_from_settings(text, settings, color)
            if img is not None:
                preview_grid = PixelGrid.from_pil_image(img)
                self.pixel_canvas.draw_floating_pixels(
                    preview_grid, self._text_pos[0], self._text_pos[1])

        dialog = TextDialog(
            self.root,
            loaded_fonts=self._text_loaded_fonts,
            on_preview=_preview,
            initial_settings={
                "font_name": "Standard 5x7",
                "font_size": self._text_font_size,
                "spacing": self._text_spacing,
                "line_height": self._text_line_height,
                "align": self._text_align,
            },
        )
        self.root.wait_window(dialog)

        if dialog.result is not None:
            settings = dialog.result
            text = settings.get("text", "")
            if text.strip():
                self._push_undo()
                color = self.palette.selected_color
                img = self._render_text_from_settings(text, settings, color)
                if img is not None:
                    self._tools["Text"].apply(
                        self.timeline.current_layer(), img,
                        self._text_pos[0], self._text_pos[1])
                # Save settings for next use
                self._text_spacing = settings["spacing"]
                self._text_line_height = settings["line_height"]
                self._text_align = settings["align"]
                self._text_font_size = settings["font_size"]

        self.pixel_canvas.clear_floating()
        self._text_mode = False
        self._render_canvas()

    def _exit_text_mode(self, commit=False):
        """Exit text mode (no-op in dialog mode, kept for compatibility)."""
        self._text_mode = False
        self.pixel_canvas.clear_floating()
        self._render_canvas()

    def _render_text_from_settings(self, text, settings, color):
        """Render text into a PIL Image from dialog settings."""
        from src.bitmap_fonts import render_text, render_text_ttf, FONT_TINY, FONT_STANDARD

        font_name = settings.get("font_name", "Standard 5x7")
        spacing = settings.get("spacing", 1)
        line_h = settings.get("line_height", 2)
        align = settings.get("align", "left")

        if font_name == "Tiny 3x5":
            return render_text(text, FONT_TINY, color,
                               spacing=spacing, line_height=line_h, align=align)
        elif font_name == "Standard 5x7":
            return render_text(text, FONT_STANDARD, color,
                               spacing=spacing, line_height=line_h, align=align)
        else:
            font_path = self._text_loaded_fonts.get(font_name)
            if font_path:
                font_size = settings.get("font_size", 12)
                return render_text_ttf(text, font_path, font_size, color,
                                       spacing=spacing, line_height=line_h,
                                       align=align)
        return None

    def _on_key_press(self, event):
        """Handle keyboard input — no-op now that text uses a dialog."""
        return

    def _draw_symmetry_axis_overlay(self):
        """Draw the symmetry axis guide line if symmetry is active."""
        if self._symmetry_mode == "off":
            self.pixel_canvas.clear_symmetry_axis()
            return
        w = self.timeline.width
        h = self.timeline.height
        ps = self.pixel_canvas.pixel_size
        axis_x = self._symmetry_axis_x if self._symmetry_mode in ("horizontal", "both") else None
        axis_y = self._symmetry_axis_y if self._symmetry_mode in ("vertical", "both") else None
        self.pixel_canvas.draw_symmetry_axis(axis_x, axis_y, w, h, ps)

    def _draw_tilemap_highlight(self, layer):
        """Highlight all cells using the currently selected tile."""
        self.pixel_canvas.delete("tile_highlight")
        tp = self.right_panel.tiles_panel
        if tp is None:
            return
        idx = tp.selected_tile_index
        if idx == 0:
            return  # Don't highlight empty cells
        tw = layer.tileset.tile_width
        th = layer.tileset.tile_height
        ps = self.pixel_canvas.pixel_size
        for row in range(layer.grid_rows):
            for col in range(layer.grid_cols):
                if layer.grid[row][col].index == idx:
                    x0 = col * tw * ps
                    y0 = row * th * ps
                    x1 = x0 + tw * ps
                    y1 = y0 + th * ps
                    self.pixel_canvas.create_rectangle(
                        x0 + 2, y0 + 2, x1 - 2, y1 - 2,
                        outline="#ffff00", width=2,
                        tags="tile_highlight")
        self.pixel_canvas.tag_raise("tile_highlight")
