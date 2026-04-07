"""Tests for Batch 6: Interop & Color features."""
import numpy as np
import pytest
import tempfile
import os
from src.export import export_png_sequence
from src.aseprite_import import load_aseprite, ASE_BLEND_MAP
from src.pixel_data import PixelGrid, IndexedPixelGrid, nearest_palette_index
from src.quantize import median_cut, quantize_to_palette
from src.layer import Layer, flatten_layers
from src.animation import AnimationTimeline, Frame
from src.project import save_project, load_project
from src.palette import Palette
from src.palette_io import load_palette, save_palette


class TestNearestPaletteIndex:
    def test_exact_match(self):
        palette = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]
        assert nearest_palette_index((0, 255, 0, 255), palette) == 1

    def test_nearest_color(self):
        palette = [(0, 0, 0, 255), (255, 255, 255, 255)]
        # (200,200,200) is closer to white
        assert nearest_palette_index((200, 200, 200, 255), palette) == 1

    def test_single_color_palette(self):
        palette = [(128, 128, 128, 255)]
        assert nearest_palette_index((0, 0, 0, 255), palette) == 0


class TestIndexedPixelGrid:
    def setup_method(self):
        self.palette = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]
        self.grid = IndexedPixelGrid(4, 4, self.palette)

    def test_init_all_transparent(self):
        assert self.grid.get_pixel(0, 0) == (0, 0, 0, 0)
        assert self.grid.get_index(0, 0) == 0

    def test_set_pixel_snaps_to_palette(self):
        self.grid.set_pixel(0, 0, (255, 0, 0, 255))  # exact red
        assert self.grid.get_index(0, 0) == 1  # 1-based
        assert self.grid.get_pixel(0, 0) == (255, 0, 0, 255)

    def test_set_pixel_transparent_sets_index_zero(self):
        self.grid.set_pixel(0, 0, (255, 0, 0, 255))
        self.grid.set_pixel(0, 0, (0, 0, 0, 0))
        assert self.grid.get_index(0, 0) == 0

    def test_set_pixel_snaps_nearest(self):
        # (200, 50, 50) is closest to red (255,0,0)
        self.grid.set_pixel(1, 1, (200, 50, 50, 255))
        assert self.grid.get_index(1, 1) == 1  # red

    def test_out_of_bounds_returns_none(self):
        assert self.grid.get_pixel(-1, 0) is None
        assert self.grid.get_pixel(0, 99) is None

    def test_to_rgba_vectorized(self):
        self.grid.set_pixel(0, 0, (255, 0, 0, 255))
        self.grid.set_pixel(1, 0, (0, 255, 0, 255))
        rgba = self.grid.to_rgba()
        assert rgba.shape == (4, 4, 4)
        assert tuple(rgba[0, 0]) == (255, 0, 0, 255)
        assert tuple(rgba[0, 1]) == (0, 255, 0, 255)
        assert tuple(rgba[1, 0]) == (0, 0, 0, 0)  # still transparent

    def test_to_pil_image(self):
        self.grid.set_pixel(0, 0, (255, 0, 0, 255))
        img = self.grid.to_pil_image()
        assert img.size == (4, 4)
        assert img.mode == "RGBA"

    def test_copy_preserves_data_and_palette(self):
        self.grid.set_pixel(0, 0, (255, 0, 0, 255))
        copy = self.grid.copy()
        assert copy.get_index(0, 0) == 1
        assert copy._palette is self.palette

    def test_extract_region(self):
        self.grid.set_pixel(1, 1, (0, 255, 0, 255))
        region = self.grid.extract_region(1, 1, 2, 2)
        assert region.width == 2
        assert region.height == 2
        assert region.get_index(0, 0) == 2  # green at (0,0) of region

    def test_paste_region(self):
        source = IndexedPixelGrid(2, 2, self.palette)
        source.set_index(0, 0, 3)  # blue
        self.grid.paste_region(source, 1, 1)
        assert self.grid.get_index(1, 1) == 3

    def test_clear(self):
        self.grid.set_pixel(0, 0, (255, 0, 0, 255))
        self.grid.clear()
        assert self.grid.get_index(0, 0) == 0

    def test_serialization_roundtrip(self):
        self.grid.set_pixel(0, 0, (255, 0, 0, 255))
        self.grid.set_pixel(1, 0, (0, 0, 255, 255))
        flat = self.grid.to_flat_indices()
        restored = IndexedPixelGrid.from_flat_indices(4, 4, flat, self.palette)
        assert restored.get_index(0, 0) == self.grid.get_index(0, 0)
        assert restored.get_index(1, 0) == self.grid.get_index(1, 0)

    def test_to_pixelgrid(self):
        self.grid.set_pixel(0, 0, (0, 255, 0, 255))
        pg = self.grid.to_pixelgrid()
        assert isinstance(pg, PixelGrid)
        assert pg.get_pixel(0, 0) == (0, 255, 0, 255)


class TestIndexedLayer:
    def setup_method(self):
        self.palette = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]

    def test_layer_default_is_rgba(self):
        layer = Layer("test", 4, 4)
        assert layer.color_mode == "rgba"
        assert isinstance(layer.pixels, PixelGrid)

    def test_layer_indexed_mode(self):
        layer = Layer("test", 4, 4, color_mode="indexed", palette=self.palette)
        assert layer.color_mode == "indexed"
        assert isinstance(layer.pixels, IndexedPixelGrid)

    def test_indexed_layer_set_get_pixel(self):
        layer = Layer("test", 4, 4, color_mode="indexed", palette=self.palette)
        layer.pixels.set_pixel(0, 0, (255, 0, 0, 255))
        assert layer.pixels.get_pixel(0, 0) == (255, 0, 0, 255)

    def test_indexed_layer_copy(self):
        layer = Layer("test", 4, 4, color_mode="indexed", palette=self.palette)
        layer.pixels.set_pixel(0, 0, (0, 255, 0, 255))
        copy = layer.copy()
        assert copy.color_mode == "indexed"
        assert isinstance(copy.pixels, IndexedPixelGrid)
        assert copy.pixels.get_pixel(0, 0) == (0, 255, 0, 255)

    def test_flatten_indexed_layer(self):
        layer = Layer("bg", 4, 4, color_mode="indexed", palette=self.palette)
        layer.pixels.set_pixel(0, 0, (255, 0, 0, 255))
        result = flatten_layers([layer], 4, 4)
        assert isinstance(result, PixelGrid)
        assert result.get_pixel(0, 0) == (255, 0, 0, 255)

    def test_flatten_mixed_rgba_and_indexed(self):
        rgba_layer = Layer("bg", 4, 4)
        rgba_layer.pixels.set_pixel(0, 0, (128, 128, 128, 255))
        idx_layer = Layer("fg", 4, 4, color_mode="indexed", palette=self.palette)
        idx_layer.pixels.set_pixel(1, 0, (0, 0, 255, 255))
        result = flatten_layers([rgba_layer, idx_layer], 4, 4)
        assert result.get_pixel(0, 0) == (128, 128, 128, 255)  # from rgba
        assert result.get_pixel(1, 0) == (0, 0, 255, 255)  # from indexed

    def test_layer_from_grid_indexed(self):
        grid = IndexedPixelGrid(4, 4, self.palette)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        layer = Layer.from_grid("test", grid)
        assert layer.color_mode == "indexed"
        assert isinstance(layer.pixels, IndexedPixelGrid)
        assert layer.pixels.get_pixel(0, 0) == (255, 0, 0, 255)


class TestTimelineIndexedMode:
    def setup_method(self):
        self.palette = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]

    def test_default_color_mode_is_rgba(self):
        tl = AnimationTimeline(8, 8)
        assert tl.color_mode == "rgba"

    def test_set_indexed_mode(self):
        tl = AnimationTimeline(8, 8)
        tl.color_mode = "indexed"
        tl.palette_ref = self.palette
        assert tl.color_mode == "indexed"

    def test_add_frame_respects_color_mode(self):
        tl = AnimationTimeline(8, 8)
        tl.color_mode = "indexed"
        tl.palette_ref = self.palette
        tl.add_frame()
        # New frame's first layer should be indexed
        frame = tl.get_frame_obj(tl.frame_count - 1)
        assert frame.layers[0].color_mode == "indexed"

    def test_add_layer_to_all_respects_color_mode(self):
        tl = AnimationTimeline(8, 8)
        tl.color_mode = "indexed"
        tl.palette_ref = self.palette
        tl.add_layer_to_all("New Layer")
        for i in range(tl.frame_count):
            frame = tl.get_frame_obj(i)
            new_layer = frame.layers[-1]
            assert new_layer.color_mode == "indexed"

    def test_frame_init_indexed(self):
        frame = Frame(8, 8, color_mode="indexed", palette=self.palette)
        assert frame.layers[0].color_mode == "indexed"

    def test_frame_add_layer_indexed(self):
        frame = Frame(8, 8, color_mode="indexed", palette=self.palette)
        layer = frame.add_layer("Layer 2")
        assert layer.color_mode == "indexed"

    def test_frame_copy_indexed(self):
        frame = Frame(8, 8, color_mode="indexed", palette=self.palette)
        frame.layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))
        copy = frame.copy()
        assert copy.color_mode == "indexed"
        assert copy.layers[0].color_mode == "indexed"
        assert copy.layers[0].pixels.get_pixel(0, 0) == (255, 0, 0, 255)


class TestProjectV4:
    def test_save_load_indexed_project(self):
        palette = Palette("Pico-8")
        tl = AnimationTimeline(4, 4)
        tl.color_mode = "indexed"
        tl.palette_ref = palette.colors
        # Replace first frame's layer with indexed
        frame = tl.get_frame_obj(0)
        frame.layers[0] = Layer("Layer 1", 4, 4, color_mode="indexed", palette=palette.colors)
        frame.layers[0].pixels.set_pixel(0, 0, palette.colors[0])

        with tempfile.NamedTemporaryFile(suffix=".retro", delete=False) as f:
            path = f.name
        try:
            save_project(path, tl, palette)
            tl2, pal2, _, _, _ = load_project(path)
            assert tl2.color_mode == "indexed"
            layer = tl2.get_frame_obj(0).layers[0]
            assert layer.color_mode == "indexed"
            assert isinstance(layer.pixels, IndexedPixelGrid)
            assert layer.pixels.get_index(0, 0) == 1  # first palette color
        finally:
            os.unlink(path)

    def test_v3_loads_as_rgba(self):
        """Existing v3 files should load as rgba mode."""
        palette = Palette("Pico-8")
        tl = AnimationTimeline(4, 4)
        # Save as v3 (default rgba mode)
        with tempfile.NamedTemporaryFile(suffix=".retro", delete=False) as f:
            path = f.name
        try:
            save_project(path, tl, palette)
            tl2, pal2, _, _, _ = load_project(path)
            assert tl2.color_mode == "rgba"
        finally:
            os.unlink(path)


class TestMedianCut:
    def test_reduces_to_target_count(self):
        rng = np.random.RandomState(42)
        pixels = rng.randint(0, 256, (100, 4), dtype=np.uint8)
        pixels[:, 3] = 255
        result = median_cut(pixels, 4)
        assert len(result) == 4
        assert all(len(c) == 4 for c in result)

    def test_skips_transparent_pixels(self):
        pixels = np.array([
            [255, 0, 0, 255],
            [0, 0, 0, 0],
            [0, 255, 0, 255],
        ], dtype=np.uint8)
        result = median_cut(pixels, 2)
        assert len(result) == 2

    def test_single_color(self):
        pixels = np.array([[100, 100, 100, 255]] * 10, dtype=np.uint8)
        result = median_cut(pixels, 1)
        assert len(result) == 1
        r, g, b, a = result[0]
        assert abs(r - 100) < 2 and abs(g - 100) < 2

    def test_two_distinct_clusters(self):
        red = np.array([[255, 0, 0, 255]] * 50, dtype=np.uint8)
        blue = np.array([[0, 0, 255, 255]] * 50, dtype=np.uint8)
        pixels = np.vstack([red, blue])
        result = median_cut(pixels, 2)
        reds = [c for c in result if c[0] > 128]
        blues = [c for c in result if c[2] > 128]
        assert len(reds) >= 1
        assert len(blues) >= 1


class TestQuantizeToPalette:
    def test_quantize_pixelgrid(self):
        grid = PixelGrid(2, 2)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        grid.set_pixel(1, 0, (0, 255, 0, 255))
        grid.set_pixel(0, 1, (0, 0, 255, 255))
        palette = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]
        indexed = quantize_to_palette(grid, palette)
        assert isinstance(indexed, IndexedPixelGrid)
        assert indexed.get_index(0, 0) == 1  # red
        assert indexed.get_index(1, 0) == 2  # green
        assert indexed.get_index(0, 1) == 3  # blue
        assert indexed.get_index(1, 1) == 0  # transparent


class TestPaletteIO:
    def setup_method(self):
        self.colors = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]

    def test_gpl_roundtrip(self):
        with tempfile.NamedTemporaryFile(suffix=".gpl", delete=False, mode="w") as f:
            path = f.name
        try:
            save_palette(path, self.colors, name="Test")
            loaded = load_palette(path)
            assert loaded == self.colors
        finally:
            os.unlink(path)

    def test_pal_roundtrip(self):
        with tempfile.NamedTemporaryFile(suffix=".pal", delete=False, mode="w") as f:
            path = f.name
        try:
            save_palette(path, self.colors)
            loaded = load_palette(path)
            assert loaded == self.colors
        finally:
            os.unlink(path)

    def test_hex_roundtrip(self):
        with tempfile.NamedTemporaryFile(suffix=".hex", delete=False, mode="w") as f:
            path = f.name
        try:
            save_palette(path, self.colors)
            loaded = load_palette(path)
            assert loaded == self.colors
        finally:
            os.unlink(path)

    def test_ase_roundtrip(self):
        with tempfile.NamedTemporaryFile(suffix=".ase", delete=False, mode="wb") as f:
            path = f.name
        try:
            save_palette(path, self.colors, name="Test")
            loaded = load_palette(path)
            for orig, loaded_c in zip(self.colors, loaded):
                for i in range(3):
                    assert abs(orig[i] - loaded_c[i]) <= 1
        finally:
            os.unlink(path)

    def test_hex_format_no_hash(self):
        with tempfile.NamedTemporaryFile(suffix=".hex", delete=False, mode="w") as f:
            path = f.name
        try:
            save_palette(path, [(255, 0, 0, 255)])
            with open(path) as f:
                content = f.read().strip()
            assert content == "ff0000"
        finally:
            os.unlink(path)

    def test_load_hex_with_hash(self):
        with tempfile.NamedTemporaryFile(suffix=".hex", delete=False, mode="w") as f:
            f.write("#ff0000\n#00ff00\n")
            path = f.name
        try:
            loaded = load_palette(path)
            assert loaded[0] == (255, 0, 0, 255)
            assert loaded[1] == (0, 255, 0, 255)
        finally:
            os.unlink(path)


from src.scripting import RetroSpriteAPI


class TestConversion:
    def test_convert_to_indexed(self):
        palette = Palette("Pico-8")
        tl = AnimationTimeline(4, 4)
        tl.get_frame_obj(0).layers[0].pixels.set_pixel(0, 0, (255, 0, 77, 255))
        api = RetroSpriteAPI(timeline=tl, palette=palette, app=None)
        api.convert_to_indexed()
        assert tl.color_mode == "indexed"
        layer = tl.get_frame_obj(0).layers[0]
        assert layer.color_mode == "indexed"
        assert isinstance(layer.pixels, IndexedPixelGrid)
        assert layer.pixels.get_index(0, 0) > 0

    def test_convert_to_rgba(self):
        palette = Palette("Pico-8")
        tl = AnimationTimeline(4, 4)
        tl.color_mode = "indexed"
        tl.palette_ref = palette.colors
        frame = tl.get_frame_obj(0)
        frame.layers[0] = Layer("Layer 1", 4, 4, color_mode="indexed", palette=palette.colors)
        frame.layers[0].pixels.set_pixel(0, 0, palette.colors[0])
        api = RetroSpriteAPI(timeline=tl, palette=palette, app=None)
        api.convert_to_rgba()
        assert tl.color_mode == "rgba"
        layer = tl.get_frame_obj(0).layers[0]
        assert layer.color_mode == "rgba"
        assert isinstance(layer.pixels, PixelGrid)

    def test_convert_to_indexed_with_num_colors(self):
        palette = Palette("Pico-8")
        tl = AnimationTimeline(4, 4)
        tl.get_frame_obj(0).layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))
        tl.get_frame_obj(0).layers[0].pixels.set_pixel(1, 0, (0, 0, 255, 255))
        api = RetroSpriteAPI(timeline=tl, palette=palette, app=None)
        api.convert_to_indexed(num_colors=4)
        assert len(palette.colors) == 4
        assert tl.color_mode == "indexed"


class TestPNGSequenceExport:
    def test_exports_correct_number_of_files(self):
        tl = AnimationTimeline(4, 4)
        tl.add_frame()  # now 2 frames
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "sprite.png")
            paths = export_png_sequence(tl, out)
            assert len(paths) == 2
            assert all(os.path.exists(p) for p in paths)
            assert paths[0].endswith("sprite_000.png")
            assert paths[1].endswith("sprite_001.png")

    def test_scale_factor(self):
        tl = AnimationTimeline(4, 4)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "sprite.png")
            paths = export_png_sequence(tl, out, scale=2)
            from PIL import Image
            img = Image.open(paths[0])
            assert img.size == (8, 8)
            img.close()

    def test_single_frame(self):
        tl = AnimationTimeline(4, 4)
        tl.get_frame_obj(0).layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "test.png")
            paths = export_png_sequence(tl, out)
            assert len(paths) == 1
            from PIL import Image
            img = Image.open(paths[0])
            assert img.getpixel((0, 0)) == (255, 0, 0, 255)


class TestCLIIntegration:
    def test_cli_export_frames_format(self):
        """Test that --format frames produces numbered PNGs."""
        tl = AnimationTimeline(4, 4)
        tl.add_frame()

        with tempfile.TemporaryDirectory() as tmpdir:
            from src.project import save_project
            retro_path = os.path.join(tmpdir, "test.retro")
            save_project(retro_path, tl, Palette("Pico-8"))

            out_path = os.path.join(tmpdir, "out.png")
            from src.cli import cmd_export
            result = cmd_export(retro_path, out_path, format="frames",
                                scale=1, frame=0, columns=0, layer=None)
            assert result == 0
            assert os.path.exists(os.path.join(tmpdir, "out_000.png"))
            assert os.path.exists(os.path.join(tmpdir, "out_001.png"))


class TestIndexedSafetyFixes:
    def setup_method(self):
        self.palette = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]

    def test_palette_remove_color(self):
        pal = Palette("Test")
        pal.colors = list(self.palette)
        pal.selected_index = 2
        pal.remove_color(2)
        assert len(pal.colors) == 2
        assert pal.selected_index == 1

    def test_palette_replace_color(self):
        pal = Palette("Test")
        pal.colors = list(self.palette)
        pal.replace_color(0, (128, 128, 128, 255))
        assert pal.colors[0] == (128, 128, 128, 255)

    def test_merge_down_indexed_layers(self):
        frame = Frame(4, 4, color_mode="indexed", palette=self.palette)
        frame.layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))
        layer2 = frame.add_layer("Top")
        layer2.pixels.set_pixel(1, 0, (0, 255, 0, 255))
        frame.merge_down(1)
        assert len(frame.layers) == 1
        assert frame.layers[0].pixels.get_pixel(0, 0) == (255, 0, 0, 255)

    def test_apply_filter_indexed_layer(self):
        tl = AnimationTimeline(4, 4)
        tl.color_mode = "indexed"
        tl.palette_ref = self.palette
        frame = tl.get_frame_obj(0)
        frame.layers[0] = Layer("L1", 4, 4, color_mode="indexed", palette=self.palette)
        frame.layers[0].pixels.set_pixel(0, 0, (255, 0, 0, 255))

        api = RetroSpriteAPI(timeline=tl, palette=Palette("Test"), app=None)
        api.palette.colors = list(self.palette)

        def identity(pg):
            return pg
        api.apply_filter(identity)
        assert frame.layers[0].pixels.get_pixel(0, 0) == (255, 0, 0, 255)

    def test_layer_from_grid_indexed(self):
        from src.pixel_data import IndexedPixelGrid
        grid = IndexedPixelGrid(4, 4, self.palette)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        layer = Layer.from_grid("test", grid)
        assert layer.color_mode == "indexed"
        assert isinstance(layer.pixels, IndexedPixelGrid)
        assert layer.pixels.get_pixel(0, 0) == (255, 0, 0, 255)


class TestCLIExportFrames:
    def test_api_export_frames(self):
        tl = AnimationTimeline(4, 4)
        palette = Palette("Pico-8")
        api = RetroSpriteAPI(timeline=tl, palette=palette, app=None)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "sprite.png")
            paths = api.export_frames(out)
            assert len(paths) == 1
            assert os.path.exists(paths[0])


class TestAsepriteImport:
    def test_blend_map_has_standard_modes(self):
        assert ASE_BLEND_MAP[0] == "normal"
        assert ASE_BLEND_MAP[1] == "multiply"
        assert ASE_BLEND_MAP[2] == "screen"
        assert ASE_BLEND_MAP.get(6, "normal") == "normal"

    def test_load_minimal_ase_file(self):
        """Create a minimal valid .ase file in memory and parse it."""
        import struct, zlib
        header = bytearray(128)
        struct.pack_into("<I", header, 0, 0)      # file size (fill later)
        struct.pack_into("<H", header, 4, 0xA5E0)  # magic
        struct.pack_into("<H", header, 6, 1)       # frame count
        struct.pack_into("<H", header, 8, 4)       # width
        struct.pack_into("<H", header, 10, 4)      # height
        struct.pack_into("<H", header, 12, 32)     # color depth (RGBA)
        struct.pack_into("<I", header, 14, 1)      # flags
        struct.pack_into("<H", header, 18, 100)    # speed
        struct.pack_into("<I", header, 28, 0)

        frame_chunks = bytearray()

        # Layer chunk (0x2004)
        layer_data = bytearray()
        layer_data += struct.pack("<H", 1)        # flags (visible)
        layer_data += struct.pack("<H", 0)        # type (normal)
        layer_data += struct.pack("<H", 0)        # child level
        layer_data += struct.pack("<H", 0)        # default width
        layer_data += struct.pack("<H", 0)        # default height
        layer_data += struct.pack("<H", 0)        # blend mode
        layer_data += struct.pack("<B", 255)      # opacity
        layer_data += bytearray(3)                # reserved
        layer_name = "Layer 1"
        layer_data += struct.pack("<H", len(layer_name))
        layer_data += layer_name.encode("utf-8")

        frame_chunks += struct.pack("<I", len(layer_data) + 6)
        frame_chunks += struct.pack("<H", 0x2004)
        frame_chunks += layer_data

        # Cel chunk (0x2005) — compressed
        cel_data = bytearray()
        cel_data += struct.pack("<H", 0)    # layer index
        cel_data += struct.pack("<h", 0)    # x
        cel_data += struct.pack("<h", 0)    # y
        cel_data += struct.pack("<B", 255)  # opacity
        cel_data += struct.pack("<H", 2)    # cel type: compressed
        cel_data += struct.pack("<h", 0)    # z-index
        cel_data += bytearray(5)            # reserved
        cel_data += struct.pack("<H", 4)    # width
        cel_data += struct.pack("<H", 4)    # height
        raw_pixels = bytes([255, 0, 0, 255] * 16)
        compressed = zlib.compress(raw_pixels)
        cel_data += compressed

        frame_chunks += struct.pack("<I", len(cel_data) + 6)
        frame_chunks += struct.pack("<H", 0x2005)
        frame_chunks += cel_data

        # Frame header
        frame_header = bytearray()
        frame_size = 16 + len(frame_chunks)
        frame_header += struct.pack("<I", frame_size)
        frame_header += struct.pack("<H", 0xF1FA)
        old_chunks = min(2, 0xFFFF)
        frame_header += struct.pack("<H", old_chunks)
        frame_header += struct.pack("<H", 100)
        frame_header += bytearray(2)
        frame_header += struct.pack("<I", 2)

        file_data = bytes(header) + bytes(frame_header) + bytes(frame_chunks)
        file_data = struct.pack("<I", len(file_data)) + file_data[4:]

        with tempfile.NamedTemporaryFile(suffix=".ase", delete=False, mode="wb") as f:
            f.write(file_data)
            path = f.name
        try:
            tl, pal = load_aseprite(path)
            assert tl.width == 4
            assert tl.height == 4
            assert tl.frame_count == 1
            assert len(tl.get_frame_obj(0).layers) == 1
            pixel = tl.get_frame_obj(0).layers[0].pixels.get_pixel(0, 0)
            assert pixel == (255, 0, 0, 255)
        finally:
            os.unlink(path)
