import numpy as np
from src.tilemap import Tileset, TileRef, TilemapLayer
from src.layer import Layer


class TestTileRef:
    def test_create_empty(self):
        ref = TileRef(0)
        assert ref.index == 0
        assert ref.flip_x is False
        assert ref.flip_y is False

    def test_create_with_flips(self):
        ref = TileRef(5, flip_x=True, flip_y=True)
        assert ref.index == 5
        assert ref.flip_x is True

    def test_pack_unpack(self):
        ref = TileRef(42, flip_x=True, flip_y=False)
        packed = ref.pack()
        unpacked = TileRef.unpack(packed)
        assert unpacked.index == 42
        assert unpacked.flip_x is True
        assert unpacked.flip_y is False


class TestTileset:
    def test_create_tileset(self):
        ts = Tileset("Test", 16, 16)
        assert ts.name == "Test"
        assert ts.tile_width == 16
        assert len(ts.tiles) == 1

    def test_add_tile(self):
        ts = Tileset("Test", 8, 8)
        tile = np.full((8, 8, 4), [255, 0, 0, 255], dtype=np.uint8)
        idx = ts.add_tile(tile)
        assert idx == 1
        assert len(ts.tiles) == 2
        assert np.array_equal(ts.tiles[1], tile)

    def test_empty_tile_is_transparent(self):
        ts = Tileset("Test", 8, 8)
        assert np.all(ts.tiles[0][:, :, 3] == 0)

    def test_find_matching(self):
        ts = Tileset("Test", 8, 8)
        tile = np.full((8, 8, 4), [0, 255, 0, 255], dtype=np.uint8)
        ts.add_tile(tile)
        found = ts.find_matching(tile)
        assert found == 1

    def test_find_matching_not_found(self):
        ts = Tileset("Test", 8, 8)
        tile = np.full((8, 8, 4), [0, 0, 255, 255], dtype=np.uint8)
        assert ts.find_matching(tile) is None

    def test_update_tile(self):
        ts = Tileset("Test", 8, 8)
        tile = np.full((8, 8, 4), [255, 0, 0, 255], dtype=np.uint8)
        idx = ts.add_tile(tile)
        new_tile = np.full((8, 8, 4), [0, 255, 0, 255], dtype=np.uint8)
        ts.update_tile(idx, new_tile)
        assert np.array_equal(ts.tiles[idx], new_tile)

    def test_remove_tile(self):
        ts = Tileset("Test", 8, 8)
        ts.add_tile(np.full((8, 8, 4), [255, 0, 0, 255], dtype=np.uint8))
        ts.add_tile(np.full((8, 8, 4), [0, 255, 0, 255], dtype=np.uint8))
        assert len(ts.tiles) == 3
        ts.remove_tile(1)
        assert len(ts.tiles) == 2

    def test_import_from_image(self):
        from PIL import Image
        img = Image.new("RGBA", (16, 8), (0, 0, 0, 0))
        for x in range(8):
            for y in range(8):
                img.putpixel((x, y), (255, 0, 0, 255))
        for x in range(8, 16):
            for y in range(8):
                img.putpixel((x, y), (0, 255, 0, 255))
        import tempfile, os
        path = os.path.join(tempfile.gettempdir(), "test_tileset.png")
        img.save(path)
        ts = Tileset.import_from_image(path, 8, 8)
        os.unlink(path)
        assert len(ts.tiles) >= 3


class TestTilemapLayer:
    def test_create_tilemap_layer(self):
        ts = Tileset("Test", 8, 8)
        tl = TilemapLayer("Tilemap 1", 32, 32, ts)
        assert tl.grid_cols == 4
        assert tl.grid_rows == 4
        assert tl.is_tilemap()

    def test_all_cells_empty_initially(self):
        ts = Tileset("Test", 8, 8)
        tl = TilemapLayer("Tilemap 1", 16, 16, ts)
        for row in tl.grid:
            for ref in row:
                assert ref.index == 0

    def test_render_empty_is_transparent(self):
        ts = Tileset("Test", 8, 8)
        tl = TilemapLayer("Tilemap 1", 16, 16, ts)
        rendered = tl.render_to_pixels()
        assert rendered.shape == (16, 16, 4)
        assert np.all(rendered[:, :, 3] == 0)

    def test_place_tile_and_render(self):
        ts = Tileset("Test", 8, 8)
        tile = np.full((8, 8, 4), [255, 0, 0, 255], dtype=np.uint8)
        idx = ts.add_tile(tile)
        tl = TilemapLayer("Tilemap 1", 16, 16, ts)
        tl.grid[0][0] = TileRef(idx)
        rendered = tl.render_to_pixels()
        assert np.all(rendered[0:8, 0:8, 0] == 255)
        assert np.all(rendered[0:8, 0:8, 3] == 255)
        assert np.all(rendered[8:16, :, 3] == 0)

    def test_flip_x_tile(self):
        ts = Tileset("Test", 4, 4)
        tile = np.zeros((4, 4, 4), dtype=np.uint8)
        tile[:, 0] = [255, 0, 0, 255]
        idx = ts.add_tile(tile)
        tl = TilemapLayer("Test", 4, 4, ts)
        tl.grid[0][0] = TileRef(idx, flip_x=True)
        rendered = tl.render_to_pixels()
        assert np.all(rendered[:, 3, 0] == 255)

    def test_copy_preserves_tilemap_data(self):
        ts = Tileset("Test", 8, 8)
        tile = np.full((8, 8, 4), [255, 0, 0, 255], dtype=np.uint8)
        ts.add_tile(tile)
        tl = TilemapLayer("Tilemap 1", 16, 16, ts)
        tl.grid[0][0] = TileRef(1)
        copy = tl.copy()
        assert copy.is_tilemap()
        assert copy.grid[0][0].index == 1
        assert copy.tileset is ts
        copy.grid[0][0] = TileRef(0)
        assert tl.grid[0][0].index == 1

    def test_pixels_property_returns_pixelgrid(self):
        ts = Tileset("Test", 8, 8)
        tl = TilemapLayer("Tilemap 1", 16, 16, ts)
        pg = tl.pixels
        assert hasattr(pg, 'to_pil_image')
        assert pg.width == 16
        assert pg.height == 16
