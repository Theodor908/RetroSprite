"""Tiles Panel for TilemapLayer editing — tileset viewer + flip controls."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog
from PIL import Image, ImageTk
import numpy as np

from src.ui.theme import (
    BG_PANEL, BG_PANEL_ALT, BG_DEEP, BORDER, TEXT_PRIMARY, TEXT_SECONDARY,
    ACCENT_CYAN, ACCENT_MAGENTA, BUTTON_BG, BUTTON_HOVER,
)


_THUMB_SIZE = 32   # px rendered size of each tile thumbnail in the grid
_THUMB_PAD  = 2    # gap between thumbnails


class TilesPanel(tk.Frame):
    """Shows the active tileset as a thumbnail grid, flip toggles, and import."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=BG_PANEL)
        self.app = app
        self.selected_tile_index: int = 0
        self.flip_x: bool = False
        self.flip_y: bool = False
        self._tile_images: list = []   # keep PhotoImage refs alive
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # ---- Title ----
        title = tk.Label(self, text="TILES", fg=ACCENT_CYAN, bg=BG_PANEL,
                         font=("Consolas", 9, "bold"))
        title.pack(fill="x", padx=4, pady=(4, 2))

        # Thin accent separator
        sep = tk.Frame(self, height=1, bg=ACCENT_CYAN)
        sep.pack(fill="x", padx=4, pady=(0, 4))

        # ---- Mode indicator ----
        self._mode_var = tk.StringVar(value="PIXELS Auto")
        self._mode_label = tk.Label(self, textvariable=self._mode_var,
                                    fg=ACCENT_MAGENTA, bg=BG_PANEL,
                                    font=("Consolas", 8))
        self._mode_label.pack(fill="x", padx=4, pady=(0, 4))

        # ---- Tile canvas (scrollable) ----
        canvas_frame = tk.Frame(self, bg=BG_PANEL, bd=0)
        canvas_frame.pack(fill="x", padx=4)

        self._tile_canvas = tk.Canvas(canvas_frame, bg=BG_PANEL_ALT,
                                      highlightthickness=1,
                                      highlightbackground=BORDER,
                                      height=150)
        _sb = ttk.Scrollbar(canvas_frame, orient="vertical",
                            command=self._tile_canvas.yview,
                            style="Neon.Vertical.TScrollbar")
        self._tile_canvas.configure(yscrollcommand=_sb.set)
        _sb.pack(side="right", fill="y")
        self._tile_canvas.pack(side="left", fill="x", expand=True)
        self._tile_canvas.bind("<Configure>", self._on_canvas_configure)
        self._tile_canvas.bind("<Button-1>", self._on_tile_click)
        # Mousewheel scroll
        self._tile_canvas.bind("<Enter>",
            lambda e: self._tile_canvas.bind_all("<MouseWheel>",
                                                  self._on_mousewheel))
        self._tile_canvas.bind("<Leave>",
            lambda e: self._tile_canvas.unbind_all("<MouseWheel>"))

        # ---- Flip toggle buttons ----
        flip_frame = tk.Frame(self, bg=BG_PANEL)
        flip_frame.pack(fill="x", padx=4, pady=(4, 2))

        tk.Label(flip_frame, text="Flip:", fg=TEXT_SECONDARY, bg=BG_PANEL,
                 font=("Consolas", 8)).pack(side="left")

        self._flip_x_btn = tk.Button(
            flip_frame, text="X", width=3,
            bg=BUTTON_BG, fg=TEXT_PRIMARY,
            activebackground=BUTTON_HOVER, activeforeground=TEXT_PRIMARY,
            font=("Consolas", 8), relief="flat",
            command=self._toggle_flip_x)
        self._flip_x_btn.pack(side="left", padx=(4, 2))

        self._flip_y_btn = tk.Button(
            flip_frame, text="Y", width=3,
            bg=BUTTON_BG, fg=TEXT_PRIMARY,
            activebackground=BUTTON_HOVER, activeforeground=TEXT_PRIMARY,
            font=("Consolas", 8), relief="flat",
            command=self._toggle_flip_y)
        self._flip_y_btn.pack(side="left", padx=2)

        # ---- Import tileset button ----
        import_btn = tk.Button(
            self, text="Import Tileset...",
            bg=BUTTON_BG, fg=TEXT_PRIMARY,
            activebackground=BUTTON_HOVER, activeforeground=TEXT_PRIMARY,
            font=("Consolas", 8), relief="flat",
            command=self._import_tileset)
        import_btn.pack(fill="x", padx=4, pady=(4, 2))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_visibility(self, layer) -> None:
        """Show this panel only when *layer* is a TilemapLayer."""
        is_tilemap = layer is not None and hasattr(layer, 'is_tilemap') and layer.is_tilemap()
        if is_tilemap:
            self.pack(fill="x", pady=(0, 2))
            self._update_mode_label(layer)
            self.refresh()
        else:
            self.pack_forget()

    def refresh(self) -> None:
        """Redraw tile thumbnails from the active tileset."""
        tileset = self._get_active_tileset()
        self._draw_tiles(tileset)

    def get_selected_flip(self) -> tuple[bool, bool]:
        """Return current (flip_x, flip_y) state."""
        return self.flip_x, self.flip_y

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_active_tileset(self):
        """Return the Tileset of the current active layer, or None."""
        try:
            frame_obj = self.app.timeline.current_frame_obj()
            layer = frame_obj.active_layer
            if hasattr(layer, 'is_tilemap') and layer.is_tilemap():
                return layer.tileset
        except Exception:
            pass
        return None

    def _update_mode_label(self, layer) -> None:
        """Sync the mode indicator with the layer's edit_mode."""
        if layer is None:
            return
        mode = getattr(layer, 'edit_mode', 'pixels')
        sub = getattr(layer, 'pixel_sub_mode', 'auto')
        if mode == 'tiles':
            self._mode_var.set("MODE: TILES  (stamp tiles)")
        else:
            self._mode_var.set("MODE: PIXELS  (draw \u2192 auto-tiles)")

    def _draw_tiles(self, tileset) -> None:
        """Render tile thumbnails onto the canvas."""
        self._tile_canvas.delete("all")
        self._tile_images.clear()

        if tileset is None:
            self._tile_canvas.create_text(
                10, 10, anchor="nw", text="(no tileset)",
                fill=TEXT_SECONDARY, font=("Consolas", 8))
            self._tile_canvas.configure(scrollregion=(0, 0, 100, 30))
            return

        tw = tileset.tile_width
        th = tileset.tile_height
        canvas_width = max(1, self._tile_canvas.winfo_width() or 160)
        cols = max(1, canvas_width // (_THUMB_SIZE + _THUMB_PAD))
        total = len(tileset.tiles)

        for i, tile_data in enumerate(tileset.tiles):
            col = i % cols
            row = i // cols
            x0 = col * (_THUMB_SIZE + _THUMB_PAD) + _THUMB_PAD
            y0 = row * (_THUMB_SIZE + _THUMB_PAD) + _THUMB_PAD

            if i == 0:
                # Empty tile — draw a "null" indicator
                bg_id = self._tile_canvas.create_rectangle(
                    x0, y0, x0 + _THUMB_SIZE, y0 + _THUMB_SIZE,
                    fill=BG_DEEP, outline=BORDER)
                self._tile_canvas.create_text(
                    x0 + _THUMB_SIZE // 2, y0 + _THUMB_SIZE // 2,
                    text="\u2205", fill=TEXT_SECONDARY,
                    font=("Consolas", 10))
            else:
                # Render tile pixel data as thumbnail
                try:
                    arr = tile_data  # shape (th, tw, 4)
                    pil_img = Image.fromarray(arr.astype(np.uint8), mode="RGBA")
                    thumb = pil_img.resize((_THUMB_SIZE, _THUMB_SIZE),
                                           Image.NEAREST)
                    photo = ImageTk.PhotoImage(thumb)
                    self._tile_images.append(photo)
                    self._tile_canvas.create_image(x0, y0, anchor="nw",
                                                   image=photo)
                except Exception:
                    self._tile_canvas.create_rectangle(
                        x0, y0, x0 + _THUMB_SIZE, y0 + _THUMB_SIZE,
                        fill=BG_DEEP, outline=BORDER)

            # Selection highlight
            outline_color = ACCENT_CYAN if i == self.selected_tile_index else BORDER
            outline_width = 2 if i == self.selected_tile_index else 1
            self._tile_canvas.create_rectangle(
                x0, y0, x0 + _THUMB_SIZE, y0 + _THUMB_SIZE,
                outline=outline_color, width=outline_width, fill="")

            # Store index in tag so click can recover it
            self._tile_canvas.addtag_withtag(f"tile_{i}",
                                              self._tile_canvas.find_closest(
                                                  x0 + _THUMB_SIZE // 2,
                                                  y0 + _THUMB_SIZE // 2)[0])

        rows_needed = (total + cols - 1) // cols
        total_height = rows_needed * (_THUMB_SIZE + _THUMB_PAD) + _THUMB_PAD
        self._tile_canvas.configure(
            scrollregion=(0, 0, canvas_width, total_height))

    def _on_canvas_configure(self, event) -> None:
        self.refresh()

    def _on_tile_click(self, event) -> None:
        """Select the tile that was clicked."""
        tileset = self._get_active_tileset()
        if tileset is None:
            return
        canvas_width = max(1, self._tile_canvas.winfo_width() or 160)
        cols = max(1, canvas_width // (_THUMB_SIZE + _THUMB_PAD))
        # Adjust for scroll offset
        y_scroll = self._tile_canvas.canvasy(event.y)
        x_scroll = self._tile_canvas.canvasx(event.x)
        col = int(x_scroll // (_THUMB_SIZE + _THUMB_PAD))
        row = int(y_scroll // (_THUMB_SIZE + _THUMB_PAD))
        idx = row * cols + col
        if 0 <= idx < len(tileset.tiles):
            self.selected_tile_index = idx
            self._draw_tiles(tileset)

    def _on_mousewheel(self, event) -> None:
        self._tile_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _toggle_flip_x(self) -> None:
        self.flip_x = not self.flip_x
        active = self.flip_x
        self._flip_x_btn.config(
            bg=ACCENT_CYAN if active else BUTTON_BG,
            fg=BG_DEEP if active else TEXT_PRIMARY)

    def _toggle_flip_y(self) -> None:
        self.flip_y = not self.flip_y
        active = self.flip_y
        self._flip_y_btn.config(
            bg=ACCENT_CYAN if active else BUTTON_BG,
            fg=BG_DEEP if active else TEXT_PRIMARY)

    def _import_tileset(self) -> None:
        """Import a tileset from a PNG/image file."""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Import Tileset",
            filetypes=[
                ("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"),
                ("All files", "*.*"),
            ],
            parent=self,
        )
        if not path:
            return

        # Ask for tile dimensions
        tw = simpledialog.askinteger("Tile Width", "Tile width (px):",
                                     parent=self, minvalue=1, maxvalue=256,
                                     initialvalue=16)
        if not tw:
            return
        th = simpledialog.askinteger("Tile Height", "Tile height (px):",
                                     parent=self, minvalue=1, maxvalue=256,
                                     initialvalue=tw)
        if not th:
            return

        name = simpledialog.askstring("Tileset Name", "Tileset name:",
                                      parent=self,
                                      initialvalue="Imported")
        if not name:
            name = "Imported"

        try:
            from src.tilemap import Tileset
            tileset = Tileset.import_from_image(path, tw, th, name=name)
            self.app.timeline.tilesets[name] = tileset

            # Assign to the active tilemap layer if possible
            frame_obj = self.app.timeline.current_frame_obj()
            layer = frame_obj.active_layer
            if hasattr(layer, 'is_tilemap') and layer.is_tilemap():
                layer.tileset = tileset
                layer.grid_cols = layer.grid_cols  # keep grid size
                layer.grid_rows = layer.grid_rows

            self.refresh()
        except Exception as exc:
            from tkinter import messagebox
            messagebox.showerror("Import Error", str(exc), parent=self)
