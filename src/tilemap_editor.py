"""Tilemap editing mixin for RetroSprite."""

import tkinter as tk
from tkinter import ttk

from src.ui.theme import (
    BG_DEEP, BG_PANEL_ALT, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, BUTTON_BG, BUTTON_HOVER,
)


class TilemapEditorMixin:
    """Tilemap layer creation dialog, tile-mode click/drag, cursor preview,
    and auto-syncing pixel edits back to tiles."""

    def _new_tilemap_layer_dialog(self):
        """Open a dialog to create a new TilemapLayer in the current project."""
        from src.tilemap import Tileset, TilemapLayer

        dialog = tk.Toplevel(self.root)
        dialog.title("New Tilemap Layer")
        dialog.geometry("320x280")
        dialog.resizable(False, False)
        dialog.configure(bg=BG_DEEP)
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="New Tilemap Layer", fg=ACCENT_CYAN, bg=BG_DEEP,
                 font=("Consolas", 11, "bold")).pack(pady=(12, 8))

        # --- Tileset source radio ---
        source_var = tk.StringVar(value="new")
        existing_names = list(self.timeline.tilesets.keys())

        src_frame = tk.Frame(dialog, bg=BG_DEEP)
        src_frame.pack(fill="x", padx=16, pady=(0, 6))

        tk.Radiobutton(src_frame, text="Create new tileset", variable=source_var,
                       value="new", bg=BG_DEEP, fg=TEXT_PRIMARY,
                       activebackground=BG_DEEP, selectcolor=BG_PANEL_ALT,
                       font=("Consolas", 9)).pack(anchor="w")

        existing_rb = tk.Radiobutton(src_frame, text="Use existing tileset",
                                     variable=source_var, value="existing",
                                     bg=BG_DEEP, fg=TEXT_PRIMARY,
                                     activebackground=BG_DEEP,
                                     selectcolor=BG_PANEL_ALT,
                                     font=("Consolas", 9),
                                     state="normal" if existing_names else "disabled")
        existing_rb.pack(anchor="w")

        existing_var = tk.StringVar(value=existing_names[0] if existing_names else "")
        existing_combo_frame = tk.Frame(dialog, bg=BG_DEEP)
        existing_combo_frame.pack(fill="x", padx=32, pady=(0, 4))
        existing_combo = ttk.Combobox(existing_combo_frame, textvariable=existing_var,
                                      values=existing_names, state="readonly", width=20)
        existing_combo.pack(side="left")

        # --- Tileset name ---
        name_frame = tk.Frame(dialog, bg=BG_DEEP)
        name_frame.pack(fill="x", padx=16, pady=(0, 4))
        tk.Label(name_frame, text="Tileset name:", fg=TEXT_SECONDARY, bg=BG_DEEP,
                 font=("Consolas", 9)).pack(side="left")
        name_var = tk.StringVar(value=f"Tileset {len(self.timeline.tilesets) + 1}")
        tk.Entry(name_frame, textvariable=name_var, width=16,
                 bg=BG_PANEL_ALT, fg=TEXT_PRIMARY, font=("Consolas", 9),
                 insertbackground=ACCENT_CYAN, highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT_CYAN
                 ).pack(side="left", padx=4)

        # --- Tile size presets + spinboxes ---
        preset_frame = tk.Frame(dialog, bg=BG_DEEP)
        preset_frame.pack(fill="x", padx=16, pady=(0, 4))
        tk.Label(preset_frame, text="Tile size:", fg=TEXT_SECONDARY, bg=BG_DEEP,
                 font=("Consolas", 9)).pack(side="left")

        tw_var = tk.IntVar(value=16)
        th_var = tk.IntVar(value=16)

        tk.Spinbox(preset_frame, from_=1, to=256, textvariable=tw_var, width=4,
                   bg=BG_PANEL_ALT, fg=TEXT_PRIMARY, font=("Consolas", 9),
                   buttonbackground=BUTTON_BG).pack(side="left", padx=(4, 0))
        tk.Label(preset_frame, text="x", fg=TEXT_SECONDARY, bg=BG_DEEP,
                 font=("Consolas", 9)).pack(side="left", padx=2)
        tk.Spinbox(preset_frame, from_=1, to=256, textvariable=th_var, width=4,
                   bg=BG_PANEL_ALT, fg=TEXT_PRIMARY, font=("Consolas", 9),
                   buttonbackground=BUTTON_BG).pack(side="left")

        # Presets dropdown
        def _apply_preset(val):
            size = int(val.split("x")[0])
            tw_var.set(size)
            th_var.set(size)

        preset_combo_frame = tk.Frame(dialog, bg=BG_DEEP)
        preset_combo_frame.pack(fill="x", padx=32, pady=(0, 4))
        preset_combo = ttk.Combobox(preset_combo_frame,
                                    values=["8x8", "16x16", "24x24", "32x32"],
                                    state="readonly", width=8)
        preset_combo.set("16x16")
        preset_combo.pack(side="left")
        preset_combo.bind("<<ComboboxSelected>>",
                          lambda e: _apply_preset(preset_combo.get()))

        # --- Buttons ---
        btn_frame = tk.Frame(dialog, bg=BG_DEEP)
        btn_frame.pack(pady=12)

        def _on_create():
            src = source_var.get()
            tw = tw_var.get()
            th = th_var.get()

            if src == "existing" and existing_var.get():
                tileset = self.timeline.tilesets[existing_var.get()]
                ts_name = existing_var.get()
            else:
                ts_name = name_var.get().strip() or f"Tileset {len(self.timeline.tilesets) + 1}"
                tileset = Tileset(ts_name, tw, th)
                self.timeline.tilesets[ts_name] = tileset

            # Create the layer in the current frame
            frame_obj = self.timeline.current_frame_obj()
            new_layer = TilemapLayer(
                ts_name,
                self.timeline.width,
                self.timeline.height,
                tileset,
            )
            frame_obj.layers.append(new_layer)
            frame_obj.active_layer_index = len(frame_obj.layers) - 1

            # Sync across all frames
            self.timeline.sync_layers()

            # Refresh UI
            self._refresh_canvas()
            self._update_layer_list()
            self.timeline_panel.refresh()
            # Show tiles panel
            self.right_panel.update_tiles_visibility(new_layer)
            self._update_status(f"Tilemap '{ts_name}' — draw pixels, tiles auto-created. Tab to switch modes.")
            dialog.destroy()

        tk.Button(btn_frame, text="Create", bg=ACCENT_CYAN, fg=BG_DEEP,
                  activebackground=ACCENT_CYAN, activeforeground=BG_DEEP,
                  font=("Consolas", 9, "bold"), relief="flat", width=10,
                  command=_on_create).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Cancel", bg=BUTTON_BG, fg=TEXT_PRIMARY,
                  activebackground=BUTTON_HOVER, activeforeground=TEXT_PRIMARY,
                  font=("Consolas", 9), relief="flat", width=8,
                  command=dialog.destroy).pack(side="left", padx=4)

        dialog.wait_window()

    def _toggle_tilemap_mode(self):
        """Cycle TilemapLayer edit mode: pixels(auto) -> pixels(manual) -> tiles -> ...
        Only acts when the active layer is a TilemapLayer."""
        frame_obj = self.timeline.current_frame_obj()
        layer = frame_obj.active_layer
        if not (hasattr(layer, 'is_tilemap') and layer.is_tilemap()):
            return  # Tab has no effect on non-tilemap layers

        mode = layer.edit_mode
        sub = layer.pixel_sub_mode

        if mode == "pixels":
            # pixels -> tiles
            layer.edit_mode = "tiles"
            # Auto-select first real tile when entering tile mode
            tp = self.right_panel.tiles_panel
            if tp is not None and tp.selected_tile_index == 0 and len(layer.tileset.tiles) > 1:
                tp.selected_tile_index = 1
            # Invalidate pixel buffer so canvas shows tile grid state
            layer.invalidate_pixel_buffer()
            self._update_status("TILES — click to stamp, Eraser to clear, Pick (I) to sample")
        else:
            # tiles -> pixels
            layer.edit_mode = "pixels"
            layer.pixel_sub_mode = "auto"
            self._update_status("PIXELS — draw normally, tiles auto-created on release. Tab for tile mode.")

        # Clean up any lingering overlays
        self.pixel_canvas.clear_floating()
        self.pixel_canvas.clear_transform_handles()

        # Update the mode indicator in the tiles panel
        if self.right_panel.tiles_panel is not None:
            self.right_panel.tiles_panel._update_mode_label(layer)
        self._render_canvas()

    # --- Tilemap drawing helpers ---

    def _on_tilemap_click(self, layer, x: int, y: int) -> None:
        """Handle a click/drag on a TilemapLayer in 'tiles' edit mode."""
        from src.tilemap import TileRef
        tw = layer.tileset.tile_width
        th = layer.tileset.tile_height
        col = x // tw
        row = y // th
        if not (0 <= row < layer.grid_rows and 0 <= col < layer.grid_cols):
            self._render_canvas()
            return

        tool = self.current_tool_name
        tiles_panel = self.right_panel.tiles_panel

        if tool == "Pen":
            if tiles_panel is not None:
                layer.grid[row][col] = TileRef(
                    tiles_panel.selected_tile_index,
                    tiles_panel.flip_x,
                    tiles_panel.flip_y,
                )
            else:
                layer.grid[row][col] = TileRef(1)

        elif tool == "Eraser":
            layer.grid[row][col] = TileRef(0)

        elif tool == "Pick":
            ref = layer.grid[row][col]
            if tiles_panel is not None:
                tiles_panel.selected_tile_index = ref.index
                tiles_panel.flip_x = ref.flip_x
                tiles_panel.flip_y = ref.flip_y
                tiles_panel.refresh()

        elif tool == "Fill":
            target_index = layer.grid[row][col].index
            fill_index = tiles_panel.selected_tile_index if tiles_panel else 1
            fill_fx = tiles_panel.flip_x if tiles_panel else False
            fill_fy = tiles_panel.flip_y if tiles_panel else False
            if target_index == fill_index:
                self._render_canvas()
                return
            visited: set = set()
            queue = [(row, col)]
            while queue:
                r, c = queue.pop(0)
                if (r, c) in visited:
                    continue
                if r < 0 or r >= layer.grid_rows or c < 0 or c >= layer.grid_cols:
                    continue
                if layer.grid[r][c].index != target_index:
                    continue
                visited.add((r, c))
                layer.grid[r][c] = TileRef(fill_index, fill_fx, fill_fy)
                queue.extend([(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)])

        layer.invalidate_pixel_buffer()
        self._render_canvas()

    def _draw_tile_cursor_preview(self, layer, x: int, y: int) -> None:
        """Draw a ghost tile preview at the hovered grid cell in tile-edit mode."""
        from PIL import Image
        tw = layer.tileset.tile_width
        th = layer.tileset.tile_height
        col = x // tw
        row = y // th
        zoom = self.pixel_canvas.pixel_size

        self.pixel_canvas.clear_overlays()
        self.pixel_canvas.clear_tile_cursor()

        if not (0 <= row < layer.grid_rows and 0 <= col < layer.grid_cols):
            return

        tiles_panel = self.right_panel.tiles_panel
        tile_image = None
        if (tiles_panel is not None
                and self.current_tool_name in ("Pen", "Fill")
                and tiles_panel.selected_tile_index > 0):
            idx = tiles_panel.selected_tile_index
            if idx < len(layer.tileset.tiles):
                import numpy as np
                arr = layer.tileset.tiles[idx].copy()
                if tiles_panel.flip_x:
                    arr = np.flip(arr, axis=1)
                if tiles_panel.flip_y:
                    arr = np.flip(arr, axis=0)
                try:
                    tile_image = Image.fromarray(arr.astype(np.uint8), "RGBA")
                except Exception:
                    tile_image = None

        self.pixel_canvas.draw_tile_cursor(col, row, tw, th, zoom, tile_image)

    def _tilemap_auto_sync(self, layer) -> None:
        """After a pixel-mode stroke on a TilemapLayer, sync tile grid.

        For each grid cell, extract the rendered pixel region from the layer's
        tileset pixel buffer and try to match it to an existing tile.  If no
        match is found, add a new tile and point the cell at it.  Afterwards,
        remove tiles that are no longer referenced by any cell.
        """
        from src.tilemap import TileRef
        import numpy as np
        tw = layer.tileset.tile_width
        th = layer.tileset.tile_height
        # Read from the writable pixel buffer (contains user's edits)
        rendered = layer.pixels._pixels  # shape (H, W, 4)

        for row in range(layer.grid_rows):
            for col in range(layer.grid_cols):
                y0 = row * th
                x0 = col * tw
                region = rendered[y0:y0 + th, x0:x0 + tw]
                # Skip fully transparent cells (treat as empty tile 0)
                if region[:, :, 3].sum() == 0:
                    layer.grid[row][col] = TileRef(0)
                    continue
                match = layer.tileset.find_matching(region)
                if match is not None:
                    # Keep flips from previous cell ref (find_matching only
                    # checks un-flipped data, so reset flips on match).
                    layer.grid[row][col] = TileRef(match, False, False)
                else:
                    new_idx = layer.tileset.add_tile(region)
                    layer.grid[row][col] = TileRef(new_idx, False, False)

        # Clean up unused tiles (except tile 0 — the empty tile)
        referenced = {ref.index
                      for row_list in layer.grid
                      for ref in row_list}
        tiles_to_remove = [
            i for i in range(len(layer.tileset.tiles) - 1, 0, -1)
            if i not in referenced
        ]
        for idx in tiles_to_remove:
            layer.tileset.remove_tile(idx)
            # Remap grid references for tiles that shifted down
            for row_list in layer.grid:
                for ref in row_list:
                    if ref.index > idx:
                        ref.index -= 1

        # Invalidate pixel buffer so next render uses updated tiles
        layer.invalidate_pixel_buffer()

        # Refresh tiles panel and auto-select first real tile if still on empty
        if self.right_panel.tiles_panel is not None:
            tp = self.right_panel.tiles_panel
            if tp.selected_tile_index == 0 and len(layer.tileset.tiles) > 1:
                tp.selected_tile_index = 1
            tp.refresh()
