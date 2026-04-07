"""Pixel canvas widget for drawing."""
from __future__ import annotations
import math
import tkinter as tk
import numpy as np
from PIL import Image, ImageDraw, ImageTk
from src.pixel_data import PixelGrid
from src.grid import GridSettings


def build_render_image(grid: PixelGrid, pixel_size: int,
                       grid_settings: 'GridSettings | None' = None,
                       onion_grid: PixelGrid | None = None,
                       onion_past_grids: list | None = None,
                       onion_future_grids: list | None = None,
                       onion_past_tint: tuple = (255, 0, 170),
                       onion_future_tint: tuple = (0, 240, 255),
                       reference: 'ReferenceImage | None' = None,
                       reference_image: Image.Image | None = None,
                       reference_opacity: float = 0.3,
                       tiled_mode: str = "off") -> Image.Image:
    """Build a PIL RGB image of the canvas at the given zoom level."""
    w, h = grid.width, grid.height
    if w == 0 or h == 0 or pixel_size <= 0:
        return Image.new("RGB", (max(1, w * max(1, pixel_size)),
                                 max(1, h * max(1, pixel_size))), (43, 43, 43))
    # Checkerboard background (white/light-gray, 1-pixel cells at source scale)
    bg = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    checker_dark = (204, 204, 204, 255)
    for cy in range(h):
        for cx in range(w):
            if (cx + cy) % 2 == 1:
                bg.putpixel((cx, cy), checker_dark)

    # Backward compat: wrap old onion_grid into onion_past_grids
    if onion_grid is not None and onion_past_grids is None:
        onion_past_grids = [onion_grid]

    # Render past onion frames with tint (nearest = most opaque)
    if onion_past_grids:
        for i, og in enumerate(onion_past_grids):
            if og.width != w or og.height != h:
                continue
            opacity = max(16, 64 - i * 24)
            onion_arr = og._pixels.copy()
            mask = onion_arr[:, :, 3] > 0
            onion_arr[mask, 0] = onion_past_tint[0]
            onion_arr[mask, 1] = onion_past_tint[1]
            onion_arr[mask, 2] = onion_past_tint[2]
            onion_arr[mask, 3] = opacity
            onion_layer = Image.fromarray(onion_arr, "RGBA")
            bg = Image.alpha_composite(bg, onion_layer)

    # Render future onion frames with tint
    if onion_future_grids:
        for i, og in enumerate(onion_future_grids):
            if og.width != w or og.height != h:
                continue
            opacity = max(16, 64 - i * 24)
            onion_arr = og._pixels.copy()
            mask = onion_arr[:, :, 3] > 0
            onion_arr[mask, 0] = onion_future_tint[0]
            onion_arr[mask, 1] = onion_future_tint[1]
            onion_arr[mask, 2] = onion_future_tint[2]
            onion_arr[mask, 3] = opacity
            onion_layer = Image.fromarray(onion_arr, "RGBA")
            bg = Image.alpha_composite(bg, onion_layer)

    # Composite reference image between background and pixel data
    # Support new ReferenceImage object or legacy (reference_image, reference_opacity) params
    if reference is not None and reference.visible:
        orig_w, orig_h = reference.image.size
        scaled_w = max(1, int(orig_w * reference.scale))
        scaled_h = max(1, int(orig_h * reference.scale))
        ref_scaled = reference.image.resize((scaled_w, scaled_h), Image.LANCZOS)
        ref_arr = np.array(ref_scaled, dtype=np.uint8)
        ref_arr[:, :, 3] = (ref_arr[:, :, 3].astype(np.float32)
                            * reference.opacity).astype(np.uint8)
        ref_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ref_layer.paste(Image.fromarray(ref_arr, "RGBA"), (reference.x, reference.y))
        bg = Image.alpha_composite(bg, ref_layer)
    elif reference_image is not None:
        ref = reference_image.copy()
        if ref.size != (w, h):
            ref = ref.resize((w, h), Image.LANCZOS)
        ref_arr = np.array(ref, dtype=np.uint8)
        ref_arr[:, :, 3] = (ref_arr[:, :, 3].astype(np.float32)
                            * reference_opacity).astype(np.uint8)
        ref_layer = Image.fromarray(ref_arr, "RGBA")
        bg = Image.alpha_composite(bg, ref_layer)

    frame_img = grid.to_pil_image()
    bg = Image.alpha_composite(bg, frame_img)

    rgb = bg.convert("RGB")
    scaled = rgb.resize((w * pixel_size, h * pixel_size), Image.NEAREST)

    gs = grid_settings
    sw, sh = scaled.size
    draw = ImageDraw.Draw(scaled)

    # Pixel grid (1x1)
    if gs is not None and gs.pixel_grid_visible and pixel_size >= gs.pixel_grid_min_zoom:
        r, g, b, a = gs.pixel_grid_color
        bg_r, bg_g, bg_b = 13, 13, 18
        f = a / 255.0
        pc = (int(bg_r * (1 - f) + r * f),
              int(bg_g * (1 - f) + g * f),
              int(bg_b * (1 - f) + b * f))
        for x in range(0, sw + 1, pixel_size):
            draw.line([(x, 0), (x, sh - 1)], fill=pc)
        for y in range(0, sh + 1, pixel_size):
            draw.line([(0, y), (sw - 1, y)], fill=pc)

    # Custom grid (NxM)
    if gs is not None and gs.custom_grid_visible and gs.custom_grid_width > 0 and gs.custom_grid_height > 0:
        r, g, b, a = gs.custom_grid_color
        bg_r, bg_g, bg_b = 13, 13, 18
        f = a / 255.0
        cc = (int(bg_r * (1 - f) + r * f),
              int(bg_g * (1 - f) + g * f),
              int(bg_b * (1 - f) + b * f))
        gw = gs.custom_grid_width * pixel_size
        gh = gs.custom_grid_height * pixel_size
        ox = gs.custom_grid_offset_x * pixel_size
        oy = gs.custom_grid_offset_y * pixel_size
        start_x = ox % gw if gw > 0 else 0
        x = start_x
        while x <= sw:
            draw.line([(x, 0), (x, sh - 1)], fill=cc, width=2)
            x += gw
        start_y = oy % gh if gh > 0 else 0
        y = start_y
        while y <= sh:
            draw.line([(0, y), (sw - 1, y)], fill=cc, width=2)
            y += gh

    if tiled_mode != "off":
        tw, th = scaled.size
        tiled = Image.new("RGB", (tw * 3, th * 3))
        for ty in range(3):
            for tx in range(3):
                tiled.paste(scaled, (tx * tw, ty * th))
        from PIL import ImageEnhance
        dimmed = ImageEnhance.Brightness(scaled).enhance(0.4)
        for ty in range(3):
            for tx in range(3):
                if tx == 1 and ty == 1:
                    continue
                tiled.paste(dimmed, (tx * tw, ty * th))
        scaled = tiled

    return scaled


def build_floating_image(source: PixelGrid, pixel_size: int) -> Image.Image:
    """Build an RGBA image for the floating paste preview."""
    img = source.to_pil_image()
    scaled = img.resize((source.width * pixel_size, source.height * pixel_size),
                        Image.NEAREST)
    return scaled


class PixelCanvas(tk.Canvas):
    """Zoomable pixel art canvas with grid overlay and scroll support."""

    def __init__(self, parent, grid: PixelGrid, pixel_size: int = 20, **kwargs):
        self.grid = grid
        self.pixel_size = pixel_size
        self.grid_settings = GridSettings()
        self._photo = None
        self._image_id = None
        self._floating_photo = None
        self._tiled_mode = "off"
        width = grid.width * pixel_size
        height = grid.height * pixel_size
        super().__init__(parent, width=width, height=height,
                         bg="#2b2b2b", highlightthickness=0, **kwargs)
        self._update_scrollregion()

        self._on_pixel_click = None
        self._on_pixel_drag = None
        self._on_pixel_release = None
        self._on_pixel_motion = None
        self._on_raw_drag = None      # (event) for Hand tool
        self._on_raw_click = None     # (event) for Hand tool

        self.bind("<Button-1>", self._handle_click)
        self.bind("<B1-Motion>", self._handle_drag)
        self.bind("<ButtonRelease-1>", self._handle_release)
        self.bind("<Motion>", self._handle_motion)

    def _update_scrollregion(self) -> None:
        w = self.grid.width * self.pixel_size
        h = self.grid.height * self.pixel_size
        if self._tiled_mode != "off":
            w *= 3
            h *= 3
        self.config(scrollregion=(0, 0, w, h))

    def set_tiled_mode(self, mode: str) -> None:
        """Set tiled mode and update scroll region accordingly."""
        self._tiled_mode = mode
        self._update_scrollregion()
        if mode != "off":
            self.xview_moveto(1 / 3)
            self.yview_moveto(1 / 3)

    def set_grid(self, grid: PixelGrid) -> None:
        self.grid = grid
        self._resize_canvas()
        self.render()

    def _resize_canvas(self) -> None:
        w = self.grid.width * self.pixel_size
        h = self.grid.height * self.pixel_size
        self.config(width=w, height=h)
        self._update_scrollregion()

    def set_pixel_size(self, size: int) -> None:
        self.pixel_size = max(1, min(64, size))
        self._resize_canvas()
        self.render()

    def zoom_in(self, event=None) -> None:
        step = max(1, self.pixel_size // 4)
        self.zoom_at(self.pixel_size + step, event)

    def zoom_out(self, event=None) -> None:
        step = max(1, self.pixel_size // 4)
        self.zoom_at(self.pixel_size - step, event)

    def zoom_at(self, new_size: int, event=None) -> None:
        """Zoom to new_size, keeping the pixel under the cursor stationary."""
        new_size = max(1, min(64, new_size))
        if new_size == self.pixel_size:
            return
        if event:
            # Get canvas coords under cursor before zoom
            cx = self.canvasx(event.x)
            cy = self.canvasy(event.y)
            # Which grid pixel is under cursor
            gx = cx / self.pixel_size
            gy = cy / self.pixel_size
            self.pixel_size = new_size
            self._resize_canvas()
            self.render()
            # New canvas position of same grid pixel
            new_cx = gx * new_size
            new_cy = gy * new_size
            # Scroll so that pixel stays under cursor
            mult = 3 if self._tiled_mode != "off" else 1
            self.xview_moveto((new_cx - event.x) / (self.grid.width * new_size * mult))
            self.yview_moveto((new_cy - event.y) / (self.grid.height * new_size * mult))
        else:
            self.pixel_size = new_size
            self._resize_canvas()
            self.render()

    def _to_grid_coords(self, event) -> tuple[int, int]:
        # Account for scroll offset
        cx = self.canvasx(event.x)
        cy = self.canvasy(event.y)
        x = int(cx) // self.pixel_size
        y = int(cy) // self.pixel_size
        if self._tiled_mode != "off":
            x = x % self.grid.width
            y = y % self.grid.height
        return x, y

    def _handle_click(self, event):
        if self._on_raw_click:
            self._on_raw_click(event)
            return
        x, y = self._to_grid_coords(event)
        if self._on_pixel_click:
            self._on_pixel_click(x, y, event.state)

    def _handle_drag(self, event):
        if self._on_raw_drag:
            self._on_raw_drag(event)
            return
        x, y = self._to_grid_coords(event)
        if self._on_pixel_drag:
            self._on_pixel_drag(x, y, event.state)

    def _handle_release(self, event):
        x, y = self._to_grid_coords(event)
        if self._on_pixel_release:
            self._on_pixel_release(x, y, event.state)

    def _handle_motion(self, event):
        x, y = self._to_grid_coords(event)
        if self._on_pixel_motion:
            self._on_pixel_motion(x, y)

    def on_pixel_click(self, callback) -> None:
        self._on_pixel_click = callback

    def on_pixel_drag(self, callback) -> None:
        self._on_pixel_drag = callback

    def on_pixel_release(self, callback) -> None:
        self._on_pixel_release = callback

    def on_pixel_motion(self, callback) -> None:
        self._on_pixel_motion = callback

    def render(self, onion_grid: PixelGrid | None = None,
               onion_past_grids=None, onion_future_grids=None,
               reference: 'ReferenceImage | None' = None,
               reference_image: Image.Image | None = None,
               reference_opacity: float = 0.3,
               tiled_mode: str = "off") -> None:
        img = build_render_image(self.grid, self.pixel_size, self.grid_settings,
                                 onion_grid,
                                 onion_past_grids=onion_past_grids,
                                 onion_future_grids=onion_future_grids,
                                 reference=reference,
                                 reference_image=reference_image,
                                 reference_opacity=reference_opacity,
                                 tiled_mode=tiled_mode)
        self._photo = ImageTk.PhotoImage(img)
        if self._image_id is None:
            self._image_id = self.create_image(0, 0, image=self._photo,
                                                anchor="nw", tags="pixel")
        else:
            self.itemconfig(self._image_id, image=self._photo)
        self.tag_raise("overlay")
        self.tag_raise("selection")
        self.tag_raise("floating")

    # --- Overlay Methods ---

    def clear_overlays(self) -> None:
        """Remove all temporary overlay items (cursor highlight, previews)."""
        self.delete("overlay")

    def clear_selection(self) -> None:
        """Remove the persistent selection overlay."""
        self.delete("selection")

    def draw_cursor_highlight(self, x: int, y: int, color: str = "#ffffff",
                              size: int = 1) -> None:
        """Draw a highlight showing the brush footprint at (x, y)."""
        ps = self.pixel_size
        half = size // 2
        for dy in range(-half, -half + size):
            for dx in range(-half, -half + size):
                px = x + dx
                py = y + dy
                if 0 <= px < self.grid.width and 0 <= py < self.grid.height:
                    self.create_rectangle(
                        px * ps, py * ps, (px + 1) * ps, (py + 1) * ps,
                        outline=color, width=2, fill="", tags="overlay"
                    )

    def draw_line_preview(self, x0: int, y0: int, x1: int, y1: int,
                          color: str = "#ffffff") -> None:
        """Draw a dashed line preview between two pixel centers."""
        ps = self.pixel_size
        half = ps // 2
        self.create_line(
            x0 * ps + half, y0 * ps + half,
            x1 * ps + half, y1 * ps + half,
            fill=color, dash=(4, 4), width=2, tags="overlay"
        )

    def draw_rect_preview(self, x0: int, y0: int, x1: int, y1: int,
                          color: str = "#ffffff") -> None:
        """Draw a dashed rectangle preview."""
        ps = self.pixel_size
        lx = min(x0, x1) * ps
        ly = min(y0, y1) * ps
        rx = (max(x0, x1) + 1) * ps
        ry = (max(y0, y1) + 1) * ps
        self.create_rectangle(
            lx, ly, rx, ry,
            outline=color, dash=(4, 4), width=2, fill="", tags="overlay"
        )

    def draw_selection(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Draw a persistent marching-ants-style selection rectangle."""
        self.delete("selection")
        ps = self.pixel_size
        lx = min(x0, x1) * ps
        ly = min(y0, y1) * ps
        rx = (max(x0, x1) + 1) * ps
        ry = (max(y0, y1) + 1) * ps
        self.create_rectangle(
            lx, ly, rx, ry,
            outline="#00bfff", dash=(6, 3), width=2, fill="", tags="selection"
        )

    def draw_wand_selection(self, pixels: set) -> None:
        """Draw per-pixel selection highlight for magic wand selections."""
        self.delete("selection")
        if not pixels:
            return
        ps = self.pixel_size
        # Build a boundary set — only draw outlines on edges of the selection
        for (px, py) in pixels:
            # Check each edge: draw a line segment if the neighbor is NOT selected
            x0 = px * ps
            y0 = py * ps
            x1 = (px + 1) * ps
            y1 = (py + 1) * ps
            if (px - 1, py) not in pixels:
                self.create_line(x0, y0, x0, y1, fill="#00f0ff",
                                 dash=(3, 3), width=2, tags="selection")
            if (px + 1, py) not in pixels:
                self.create_line(x1, y0, x1, y1, fill="#00f0ff",
                                 dash=(3, 3), width=2, tags="selection")
            if (px, py - 1) not in pixels:
                self.create_line(x0, y0, x1, y0, fill="#00f0ff",
                                 dash=(3, 3), width=2, tags="selection")
            if (px, py + 1) not in pixels:
                self.create_line(x0, y1, x1, y1, fill="#00f0ff",
                                 dash=(3, 3), width=2, tags="selection")

    def draw_lasso_preview(self, points: list) -> None:
        """Draw the in-progress lasso path as overlay lines."""
        self.delete("overlay")
        if len(points) < 2:
            return
        ps = self.pixel_size
        for i in range(len(points) - 1):
            x0 = points[i][0] * ps + ps // 2
            y0 = points[i][1] * ps + ps // 2
            x1 = points[i + 1][0] * ps + ps // 2
            y1 = points[i + 1][1] * ps + ps // 2
            self.create_line(x0, y0, x1, y1, fill="#00f0ff",
                             dash=(3, 3), width=1, tags="overlay")

    def draw_floating_pixels(self, source: PixelGrid, gx: int, gy: int) -> None:
        """Draw a floating pixel grid overlay at grid position (gx, gy)."""
        self.delete("floating")
        ps = self.pixel_size
        img = build_floating_image(source, ps)
        self._floating_photo = ImageTk.PhotoImage(img)
        self.create_image(gx * ps, gy * ps, image=self._floating_photo,
                          anchor="nw", tags="floating")
        # Draw bounding box around the floating selection
        self.create_rectangle(
            gx * ps, gy * ps,
            (gx + source.width) * ps, (gy + source.height) * ps,
            outline="#00bfff", dash=(4, 4), width=2, fill="",
            tags="floating"
        )

    def clear_floating(self) -> None:
        """Remove the floating paste overlay."""
        self.delete("floating")

    # --- Rotation Handle Overlay ---

    def draw_rotation_handles(self, bounds: tuple, angle: float,
                              pivot: tuple, zoom: int) -> None:
        """Draw a rotated bounding box with corner handles and a pivot dot.

        Args:
            bounds: (x, y, w, h) in grid coordinates
            angle: current rotation angle in degrees
            pivot: (px, py) pivot point in grid coordinates
            zoom: pixel_size (screen pixels per grid pixel)
        """
        self.delete("rotation_handle")
        bx, by, bw, bh = bounds
        ps = zoom

        # Compute the four corners of the bounding box in screen coords
        corners_grid = [
            (bx, by),
            (bx + bw, by),
            (bx + bw, by + bh),
            (bx, by + bh),
        ]

        # Pivot in screen coords
        pvx = pivot[0] * ps
        pvy = pivot[1] * ps

        rad = math.radians(-angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        def rotate_point(gx, gy):
            """Rotate a grid point around the pivot, return screen coords."""
            sx = gx * ps
            sy = gy * ps
            dx = sx - pvx
            dy = sy - pvy
            rx = dx * cos_a - dy * sin_a + pvx
            ry = dx * sin_a + dy * cos_a + pvy
            return rx, ry

        screen_corners = [rotate_point(gx, gy) for gx, gy in corners_grid]

        # Draw dashed bounding box lines
        for i in range(4):
            x0, y0 = screen_corners[i]
            x1, y1 = screen_corners[(i + 1) % 4]
            self.create_line(
                x0, y0, x1, y1,
                fill="#00f0ff", dash=(6, 3), width=2,
                tags="rotation_handle"
            )

        # Draw corner handle circles (4px radius at screen scale)
        handle_r = 4
        for sx, sy in screen_corners:
            self.create_oval(
                sx - handle_r, sy - handle_r,
                sx + handle_r, sy + handle_r,
                fill="#00f0ff", outline="#ffffff", width=1,
                tags="rotation_handle"
            )

        # Draw pivot dot (3px radius, magenta)
        pivot_r = 3
        self.create_oval(
            pvx - pivot_r, pvy - pivot_r,
            pvx + pivot_r, pvy + pivot_r,
            fill="#ff00ff", outline="#ffffff", width=1,
            tags="rotation_handle"
        )

        # Ensure handles are on top
        self.tag_raise("rotation_handle")

    def clear_rotation_handles(self) -> None:
        """Remove rotation overlay handles."""
        self.delete("rotation_handle")

    # --- Selection Transform Handle Overlay ---

    def draw_transform_handles(self, corners: list,
                                pivot: tuple,
                                position: tuple,
                                zoom: int) -> None:
        """Draw transform bounding box with corner circles, midpoint squares, and pivot.

        Args:
            corners: 4 canvas-coordinate corners from get_transform_bounding_box
            pivot: (px, py) pivot relative to image origin
            position: (x, y) canvas position of the transform
            zoom: pixel_size (screen pixels per grid pixel)
        """
        self.delete("transform_handle")
        ps = zoom

        # Convert canvas coords to screen coords
        sc = [(cx * ps, cy * ps) for cx, cy in corners]

        # Draw dashed bounding box lines
        for i in range(4):
            x0, y0 = sc[i]
            x1, y1 = sc[(i + 1) % 4]
            self.create_line(x0, y0, x1, y1,
                             fill="#00f0ff", dash=(6, 3), width=2,
                             tags="transform_handle")

        # Corner circles (filled, for scale)
        handle_r = 4
        for sx, sy in sc:
            self.create_oval(sx - handle_r, sy - handle_r,
                             sx + handle_r, sy + handle_r,
                             fill="#00f0ff", outline="#ffffff", width=1,
                             tags="transform_handle")

        # Midpoint squares (for axis scale)
        sq_r = 3
        for i in range(4):
            mx = (sc[i][0] + sc[(i + 1) % 4][0]) / 2
            my = (sc[i][1] + sc[(i + 1) % 4][1]) / 2
            self.create_rectangle(mx - sq_r, my - sq_r,
                                  mx + sq_r, my + sq_r,
                                  fill="#00f0ff", outline="#ffffff", width=1,
                                  tags="transform_handle")

        # Pivot dot (magenta circle)
        pvx = (position[0] + pivot[0]) * ps
        pvy = (position[1] + pivot[1]) * ps
        pivot_r = 3
        self.create_oval(pvx - pivot_r, pvy - pivot_r,
                         pvx + pivot_r, pvy + pivot_r,
                         fill="#ff00ff", outline="#ffffff", width=1,
                         tags="transform_handle")

        self.tag_raise("transform_handle")

    def clear_transform_handles(self) -> None:
        """Remove selection transform overlay handles."""
        self.delete("transform_handle")

    # --- Symmetry Axis Guide ---

    def draw_symmetry_axis(self, axis_x: int | None, axis_y: int | None,
                            canvas_w: int, canvas_h: int, zoom: int) -> None:
        """Draw dashed magenta axis guide lines."""
        self.delete("symmetry_axis")
        color = "#ff00ff"

        if axis_x is not None:
            sx = axis_x * zoom
            self.create_line(sx, 0, sx, canvas_h * zoom,
                             fill=color, dash=(4, 4), width=1,
                             tags="symmetry_axis")

        if axis_y is not None:
            sy = axis_y * zoom
            self.create_line(0, sy, canvas_w * zoom, sy,
                             fill=color, dash=(4, 4), width=1,
                             tags="symmetry_axis")

        self.tag_raise("symmetry_axis")

    def clear_symmetry_axis(self) -> None:
        """Remove symmetry axis overlay."""
        self.delete("symmetry_axis")

    # --- Tile Grid Overlay ---

    def draw_tile_grid(self, tile_w: int, tile_h: int,
                       canvas_w: int, canvas_h: int,
                       zoom: int,
                       offset_x: int = 0, offset_y: int = 0) -> None:
        """Draw a dashed cyan tile grid overlay at tile boundaries.

        Args:
            tile_w: tile width in canvas (grid) pixels
            tile_h: tile height in canvas (grid) pixels
            canvas_w: canvas width in grid pixels
            canvas_h: canvas height in grid pixels
            zoom: pixel_size (screen pixels per grid pixel)
            offset_x: horizontal scroll offset in screen pixels (unused; lines
                      always cover the full canvas image area)
            offset_y: vertical scroll offset in screen pixels
        """
        self.delete("tile_grid")
        # Only draw when each tile is at least 8 screen pixels wide/tall
        if tile_w * zoom < 8 or tile_h * zoom < 8:
            return

        color = "#00d4ff"
        screen_w = canvas_w * zoom
        screen_h = canvas_h * zoom

        # Vertical lines at column boundaries
        col = 0
        while col <= canvas_w:
            sx = col * zoom
            self.create_line(sx, 0, sx, screen_h,
                             fill=color, dash=(2, 4), width=1,
                             tags="tile_grid")
            col += tile_w

        # Horizontal lines at row boundaries
        row = 0
        while row <= canvas_h:
            sy = row * zoom
            self.create_line(0, sy, screen_w, sy,
                             fill=color, dash=(2, 4), width=1,
                             tags="tile_grid")
            row += tile_h

        # Ensure grid is above the pixel image but below other overlays
        self.tag_raise("tile_grid")
        self.tag_raise("overlay")
        self.tag_raise("selection")
        self.tag_raise("floating")

    def clear_tile_grid(self) -> None:
        """Remove the tile grid overlay."""
        self.delete("tile_grid")

    def draw_tile_cursor(self, col: int, row: int,
                         tile_w: int, tile_h: int,
                         zoom: int,
                         tile_image=None) -> None:
        """Draw a ghost tile preview at grid cell (col, row).

        Args:
            col: grid column index
            row: grid row index
            tile_w: tile width in canvas pixels
            tile_h: tile height in canvas pixels
            zoom: pixel_size
            tile_image: optional PIL Image to render as ghost (semi-transparent);
                        if None only draws an outline highlight.
        """
        self.delete("tile_cursor")
        x0 = col * tile_w * zoom
        y0 = row * tile_h * zoom
        x1 = x0 + tile_w * zoom
        y1 = y0 + tile_h * zoom

        if tile_image is not None:
            from PIL import Image, ImageTk
            # Scale to screen size
            ghost = tile_image.resize((tile_w * zoom, tile_h * zoom),
                                      Image.NEAREST).convert("RGBA")
            # Apply reduced alpha for ghost effect
            import numpy as np
            arr = np.array(ghost, dtype=np.uint8)
            arr[:, :, 3] = (arr[:, :, 3].astype(np.float32) * 0.5).astype(np.uint8)
            ghost = Image.fromarray(arr, "RGBA")
            self._tile_cursor_photo = ImageTk.PhotoImage(ghost)
            self.create_image(x0, y0, image=self._tile_cursor_photo,
                              anchor="nw", tags="tile_cursor")

        # Cyan highlight border
        self.create_rectangle(x0, y0, x1, y1,
                              outline="#00d4ff", width=2, fill="",
                              tags="tile_cursor")
        self.tag_raise("tile_cursor")

    def clear_tile_cursor(self) -> None:
        """Remove the tile cursor preview."""
        self.delete("tile_cursor")

    def hit_test_rotation_handle(self, sx: float, sy: float,
                                  bounds: tuple, angle: float,
                                  pivot: tuple, zoom: int,
                                  threshold: float = 8.0) -> str | None:
        """Test if screen coords (sx, sy) hit a rotation handle element.

        Returns:
            "corner:<index>" if a corner handle is hit,
            "pivot" if the pivot dot is hit,
            None otherwise.
        """
        bx, by, bw, bh = bounds
        ps = zoom

        corners_grid = [
            (bx, by),
            (bx + bw, by),
            (bx + bw, by + bh),
            (bx, by + bh),
        ]

        pvx = pivot[0] * ps
        pvy = pivot[1] * ps

        rad = math.radians(-angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        def rotate_point(gx, gy):
            sxp = gx * ps
            syp = gy * ps
            dx = sxp - pvx
            dy = syp - pvy
            rx = dx * cos_a - dy * sin_a + pvx
            ry = dx * sin_a + dy * cos_a + pvy
            return rx, ry

        # Check pivot first (smaller target, higher priority)
        dist = math.hypot(sx - pvx, sy - pvy)
        if dist <= threshold:
            return "pivot"

        # Check corners
        for i, (gx, gy) in enumerate(corners_grid):
            cx, cy = rotate_point(gx, gy)
            dist = math.hypot(sx - cx, sy - cy)
            if dist <= threshold:
                return f"corner:{i}"

        return None
