"""Tilemap layer support for RetroSprite."""
from __future__ import annotations
import numpy as np
from PIL import Image
from src.pixel_data import PixelGrid
from src.layer import Layer


class TileRef:
    """Reference to a tile in a tileset, with flip transforms."""

    def __init__(self, index: int = 0, flip_x: bool = False, flip_y: bool = False):
        self.index = index
        self.flip_x = flip_x
        self.flip_y = flip_y

    def pack(self) -> int:
        """Pack into uint32: [flip_y:1][flip_x:1][unused:14][index:16]."""
        val = self.index & 0xFFFF
        if self.flip_x:
            val |= (1 << 30)
        if self.flip_y:
            val |= (1 << 31)
        return val

    @classmethod
    def unpack(cls, packed: int) -> TileRef:
        index = packed & 0xFFFF
        flip_x = bool(packed & (1 << 30))
        flip_y = bool(packed & (1 << 31))
        return cls(index, flip_x, flip_y)

    def copy(self) -> TileRef:
        return TileRef(self.index, self.flip_x, self.flip_y)


class Tileset:
    """A collection of same-size tile images."""

    def __init__(self, name: str, tile_width: int, tile_height: int):
        self.name = name
        self.tile_width = tile_width
        self.tile_height = tile_height
        self.tiles: list[np.ndarray] = [
            np.zeros((tile_height, tile_width, 4), dtype=np.uint8)
        ]

    def add_tile(self, pixels: np.ndarray) -> int:
        self.tiles.append(pixels.copy())
        return len(self.tiles) - 1

    def remove_tile(self, index: int) -> None:
        if index > 0 and index < len(self.tiles):
            self.tiles.pop(index)

    def update_tile(self, index: int, pixels: np.ndarray) -> None:
        if 0 < index < len(self.tiles):
            self.tiles[index] = pixels.copy()

    def find_matching(self, pixels: np.ndarray) -> int | None:
        for i, tile in enumerate(self.tiles):
            if i == 0:
                continue
            if np.array_equal(tile, pixels):
                return i
        return None

    @classmethod
    def import_from_image(cls, image_path: str, tile_w: int, tile_h: int,
                          name: str = "Imported") -> Tileset:
        img = Image.open(image_path).convert("RGBA")
        tileset = cls(name, tile_w, tile_h)

        for y in range(0, img.height, tile_h):
            for x in range(0, img.width, tile_w):
                if x + tile_w > img.width or y + tile_h > img.height:
                    continue
                tile = np.array(img.crop((x, y, x + tile_w, y + tile_h)),
                                dtype=np.uint8)
                if tile[:, :, 3].sum() == 0:
                    continue
                if tileset.find_matching(tile) is None:
                    tileset.add_tile(tile)

        return tileset


class TilemapLayer(Layer):
    """A layer that stores tile references instead of raw pixels."""

    def __init__(self, name: str, width: int, height: int, tileset: Tileset):
        # We must set tileset and grid dimensions BEFORE calling super().__init__()
        # because super().__init__() will call self.pixels = ... which triggers our
        # @property setter. The setter is a no-op, so that's fine, but we need
        # the tileset attributes ready for the @property getter in case it is
        # accessed during init.
        self.tileset = tileset
        self.grid_cols = width // tileset.tile_width
        self.grid_rows = height // tileset.tile_height
        self.grid: list[list[TileRef]] = [
            [TileRef(0) for _ in range(self.grid_cols)]
            for _ in range(self.grid_rows)
        ]
        self.edit_mode: str = "pixels"
        self.pixel_sub_mode: str = "auto"
        self._pixel_buffer: PixelGrid | None = None  # writable cache for pixel mode

        # Now call super().__init__. It will do self.pixels = PixelGrid(...),
        # which hits our @pixels.setter (no-op during init). All other Layer
        # attributes (visible, opacity, etc.) are set normally.
        super().__init__(name, width, height)

    def is_tilemap(self) -> bool:
        return True

    @property
    def pixels(self) -> PixelGrid:
        """Return a writable pixel buffer.

        In pixel edit mode, tools write directly to this buffer.
        The buffer is initialized from the tile grid on first access
        and persists until invalidated by tile-mode changes.
        """
        if self._pixel_buffer is None:
            w = self.grid_cols * self.tileset.tile_width
            h = self.grid_rows * self.tileset.tile_height
            pg = PixelGrid(w, h)
            pg._pixels = self.render_to_pixels()
            self._pixel_buffer = pg
        return self._pixel_buffer

    @pixels.setter
    def pixels(self, value) -> None:
        """Allow setting pixels (used by undo restore and Layer.__init__)."""
        if isinstance(value, PixelGrid):
            self._pixel_buffer = value

    def invalidate_pixel_buffer(self) -> None:
        """Clear the pixel buffer so it re-renders from the tile grid."""
        self._pixel_buffer = None

    def render_to_pixels(self) -> np.ndarray:
        """Resolve tile grid into a pixel buffer."""
        tw, th = self.tileset.tile_width, self.tileset.tile_height
        w = self.grid_cols * tw
        h = self.grid_rows * th
        result = np.zeros((h, w, 4), dtype=np.uint8)

        for row in range(self.grid_rows):
            for col in range(self.grid_cols):
                ref = self.grid[row][col]
                if ref.index == 0 or ref.index >= len(self.tileset.tiles):
                    continue
                tile = self.tileset.tiles[ref.index].copy()
                if ref.flip_x:
                    tile = np.flip(tile, axis=1)
                if ref.flip_y:
                    tile = np.flip(tile, axis=0)
                y0 = row * th
                x0 = col * tw
                result[y0:y0 + th, x0:x0 + tw] = tile

        return result

    def copy(self) -> TilemapLayer:
        """Deep-copy grid, share tileset reference."""
        new = TilemapLayer(
            f"{self.name} Copy",
            self.grid_cols * self.tileset.tile_width,
            self.grid_rows * self.tileset.tile_height,
            self.tileset,
        )
        new.grid = [[ref.copy() for ref in row] for row in self.grid]
        new.visible = self.visible
        new.opacity = self.opacity
        new.blend_mode = self.blend_mode
        new.locked = self.locked
        new.depth = self.depth
        new.is_group = self.is_group
        new.edit_mode = self.edit_mode
        new.pixel_sub_mode = self.pixel_sub_mode
        import copy as copy_mod
        new.effects = copy_mod.deepcopy(self.effects)
        return new
