"""Tests for Batch 7: File Formats & Export features."""
import numpy as np
import pytest
import struct
import tempfile
import os
import gc
from PIL import Image

from src.animation import AnimationTimeline, Frame
from src.layer import Layer
from src.palette import Palette
from src.export import export_png_single


@pytest.fixture
def tmp_dir():
    """Temp directory that handles Windows file locks."""
    d = tempfile.mkdtemp()
    yield d
    gc.collect()
    import shutil
    shutil.rmtree(d, ignore_errors=True)


class TestExportPNGSingle:
    def setup_method(self):
        self.timeline = AnimationTimeline(8, 8)
        frame = self.timeline.get_frame_obj(0)
        frame.active_layer.pixels.set_pixel(0, 0, (255, 0, 0, 255))

    def test_export_1x(self, tmp_dir):
        path = os.path.join(tmp_dir, "out.png")
        export_png_single(self.timeline, path, frame=0, scale=1)
        img = Image.open(path)
        assert img.size == (8, 8)
        assert img.getpixel((0, 0))[:3] == (255, 0, 0)
        img.close()

    def test_export_2x(self, tmp_dir):
        path = os.path.join(tmp_dir, "out.png")
        export_png_single(self.timeline, path, frame=0, scale=2)
        img = Image.open(path)
        assert img.size == (16, 16)
        img.close()

    def test_export_4x(self, tmp_dir):
        path = os.path.join(tmp_dir, "out.png")
        export_png_single(self.timeline, path, frame=0, scale=4)
        img = Image.open(path)
        assert img.size == (32, 32)
        img.close()

    def test_export_specific_layer(self, tmp_dir):
        frame = self.timeline.get_frame_obj(0)
        frame.add_layer("Layer 2")
        frame.layers[1].pixels.set_pixel(1, 1, (0, 255, 0, 255))
        path = os.path.join(tmp_dir, "out.png")
        export_png_single(self.timeline, path, frame=0, scale=1,
                          layer="Layer 2")
        img = Image.open(path)
        assert img.getpixel((1, 1))[:3] == (0, 255, 0)
        assert img.getpixel((0, 0))[3] == 0
        img.close()


class TestGIFPerFrameDuration:
    def test_export_gif_uses_per_frame_duration(self, tmp_dir):
        timeline = AnimationTimeline(4, 4)
        timeline.add_frame()
        timeline.get_frame_obj(0).duration_ms = 200
        timeline.get_frame_obj(1).duration_ms = 500
        timeline.get_frame_obj(0).active_layer.pixels.set_pixel(0, 0, (255, 0, 0, 255))
        timeline.get_frame_obj(1).active_layer.pixels.set_pixel(0, 0, (0, 255, 0, 255))
        path = os.path.join(tmp_dir, "out.gif")
        timeline.export_gif(path, fps=10, scale=1)
        gif = Image.open(path)
        gif.seek(0)
        d0 = gif.info.get("duration", 100)
        gif.seek(1)
        d1 = gif.info.get("duration", 100)
        gif.close()
        assert d0 == 200
        assert d1 == 500


from src.animated_export import export_webp, export_apng


class TestWebPExport:
    def setup_method(self):
        self.timeline = AnimationTimeline(4, 4)
        self.timeline.add_frame()
        self.timeline.get_frame_obj(0).active_layer.pixels.set_pixel(
            0, 0, (255, 0, 0, 255))
        self.timeline.get_frame_obj(1).active_layer.pixels.set_pixel(
            0, 0, (0, 255, 0, 255))

    def test_export_webp_creates_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "out.webp")
        export_webp(self.timeline, path, scale=1)
        assert os.path.exists(path)
        img = Image.open(path)
        assert img.format == "WEBP"
        img.close()

    def test_export_webp_frame_count(self, tmp_dir):
        path = os.path.join(tmp_dir, "out.webp")
        export_webp(self.timeline, path, scale=1)
        img = Image.open(path)
        n = 0
        try:
            while True:
                img.seek(n)
                n += 1
        except EOFError:
            pass
        img.close()
        assert n == 2

    def test_export_webp_scaled(self, tmp_dir):
        path = os.path.join(tmp_dir, "out.webp")
        export_webp(self.timeline, path, scale=2)
        img = Image.open(path)
        assert img.size == (8, 8)
        img.close()


class TestAPNGExport:
    def setup_method(self):
        self.timeline = AnimationTimeline(4, 4)
        self.timeline.add_frame()
        self.timeline.get_frame_obj(0).active_layer.pixels.set_pixel(
            0, 0, (255, 0, 0, 255))
        self.timeline.get_frame_obj(1).active_layer.pixels.set_pixel(
            0, 0, (0, 255, 0, 255))

    def test_export_apng_creates_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "out.apng")
        export_apng(self.timeline, path, scale=1)
        assert os.path.exists(path)

    def test_export_apng_frame_count(self, tmp_dir):
        path = os.path.join(tmp_dir, "out.apng")
        export_apng(self.timeline, path, scale=1)
        img = Image.open(path)
        n_frames = getattr(img, 'n_frames', 1)
        img.close()
        assert n_frames == 2

    def test_export_apng_scaled(self, tmp_dir):
        path = os.path.join(tmp_dir, "out.apng")
        export_apng(self.timeline, path, scale=2)
        img = Image.open(path)
        size = img.size
        img.close()
        assert size == (8, 8)


def _create_test_psd(path, width, height, color=(255, 0, 0, 255), mode="RGBA"):
    """Create a minimal PSD file with a flat composite image."""
    if mode == "RGB":
        channels = 3
        pixel_data = []
        for c in range(3):
            for _ in range(height):
                for _ in range(width):
                    pixel_data.append(color[c])
    else:  # RGBA
        channels = 4
        pixel_data = []
        for c in range(4):
            for _ in range(height):
                for _ in range(width):
                    pixel_data.append(color[c])

    with open(path, 'wb') as f:
        f.write(b'8BPS')
        f.write(struct.pack('>H', 1))
        f.write(b'\x00' * 6)
        f.write(struct.pack('>H', channels))
        f.write(struct.pack('>I', height))
        f.write(struct.pack('>I', width))
        f.write(struct.pack('>H', 8))
        f.write(struct.pack('>H', 3))
        f.write(struct.pack('>I', 0))
        f.write(struct.pack('>I', 0))
        f.write(struct.pack('>I', 0))
        f.write(struct.pack('>H', 0))
        f.write(bytes(pixel_data))


from src.psd_import import load_psd, PSD_BLEND_MAP


class TestPSDImport:
    def test_load_psd_basic(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.psd")
        _create_test_psd(path, 8, 8, color=(255, 0, 0, 255))
        timeline, palette = load_psd(path)
        assert timeline.width == 8
        assert timeline.height == 8
        assert timeline.frame_count == 1
        assert len(palette.colors) > 0

    def test_load_psd_pixel_data(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.psd")
        _create_test_psd(path, 4, 4, color=(0, 255, 0, 255))
        timeline, palette = load_psd(path)
        frame = timeline.get_frame_obj(0)
        found = False
        for layer in frame.layers:
            px = layer.pixels.get_pixel(0, 0)
            if px and px[1] == 255:
                found = True
                break
        assert found, "Green pixel not found in any layer"

    def test_load_psd_dimensions(self, tmp_dir):
        for size in [(16, 16), (32, 32), (64, 48)]:
            path = os.path.join(tmp_dir, f"test_{size[0]}x{size[1]}.psd")
            _create_test_psd(path, size[0], size[1],
                             color=(128, 128, 128, 255))
            timeline, palette = load_psd(path)
            assert timeline.width == size[0]
            assert timeline.height == size[1]


class TestPSDBlendMap:
    def test_known_modes(self):
        assert PSD_BLEND_MAP["normal"] == "normal"
        assert PSD_BLEND_MAP["multiply"] == "multiply"
        assert PSD_BLEND_MAP["screen"] == "screen"
        assert PSD_BLEND_MAP["overlay"] == "overlay"
        assert PSD_BLEND_MAP["darken"] == "darken"
        assert PSD_BLEND_MAP["lighten"] == "lighten"
        assert PSD_BLEND_MAP["difference"] == "difference"
        assert PSD_BLEND_MAP["linear dodge"] == "addition"
        assert PSD_BLEND_MAP["subtract"] == "subtract"

    def test_fallback_is_normal(self):
        assert "color burn" not in PSD_BLEND_MAP


class TestPSDColorModes:
    def test_rgb_psd(self, tmp_dir):
        path = os.path.join(tmp_dir, "rgb.psd")
        _create_test_psd(path, 4, 4, color=(255, 0, 0), mode="RGB")
        timeline, palette = load_psd(path)
        assert timeline.width == 4
        frame = timeline.get_frame_obj(0)
        px = frame.layers[0].pixels.get_pixel(0, 0)
        assert px[0] == 255
        assert px[3] == 255

    def test_rgba_psd(self, tmp_dir):
        path = os.path.join(tmp_dir, "rgba.psd")
        _create_test_psd(path, 4, 4, color=(0, 0, 255, 128))
        timeline, palette = load_psd(path)
        frame = timeline.get_frame_obj(0)
        px = frame.layers[0].pixels.get_pixel(0, 0)
        assert px[2] == 255
        assert px[3] == 128


from src.cli import _detect_format, build_parser


class TestCLINewFormats:
    def test_detect_format_webp(self):
        assert _detect_format("output.webp") == "webp"

    def test_detect_format_apng(self):
        assert _detect_format("output.apng") == "apng"

    def test_detect_format_png_unchanged(self):
        assert _detect_format("output.png") == "png"

    def test_detect_format_gif_unchanged(self):
        assert _detect_format("output.gif") == "gif"

    def test_export_parser_has_webp(self):
        parser = build_parser()
        args = parser.parse_args(["export", "in.retro", "out.webp", "--format", "webp"])
        assert args.format == "webp"

    def test_export_parser_has_apng(self):
        parser = build_parser()
        args = parser.parse_args(["export", "in.retro", "out.apng", "--format", "apng"])
        assert args.format == "apng"

    def test_batch_parser_has_webp(self):
        parser = build_parser()
        args = parser.parse_args(["batch", "indir", "outdir", "--format", "webp"])
        assert args.format == "webp"

    def test_batch_parser_has_apng(self):
        parser = build_parser()
        args = parser.parse_args(["batch", "indir", "outdir", "--format", "apng"])
        assert args.format == "apng"


from src.ui.export_dialog import ExportSettings


class TestExportSettings:
    def test_default_values(self):
        settings = ExportSettings(
            format="png", scale=1, frame=0, layer=None,
            columns=0, output_path="/tmp/out.png"
        )
        assert settings.format == "png"
        assert settings.scale == 1
        assert settings.frame == 0
        assert settings.layer is None
        assert settings.columns == 0
        assert settings.output_path == "/tmp/out.png"

    def test_all_formats(self):
        for fmt in ["png", "gif", "webp", "apng", "sheet", "frames"]:
            s = ExportSettings(format=fmt, scale=2, frame=0, layer=None,
                               columns=0, output_path=f"/tmp/out.{fmt}")
            assert s.format == fmt

    def test_layer_name(self):
        s = ExportSettings(format="png", scale=1, frame=0, layer="Layer 2",
                           columns=0, output_path="/tmp/out.png")
        assert s.layer == "Layer 2"
