"""Tests for PIL-based canvas rendering pipeline."""
import pytest
from PIL import Image
from src.pixel_data import PixelGrid
from src.canvas import build_render_image, build_floating_image
from src.reference_image import ReferenceImage
from src.grid import GridSettings


class TestBuildRenderImage:
    def test_empty_grid_returns_bg_color(self):
        """Empty grid should produce checkerboard background (white or light gray)."""
        grid = PixelGrid(4, 4)
        img = build_render_image(grid, pixel_size=10, grid_settings=None)
        assert img.size == (40, 40)
        px = img.getpixel((5, 5))
        # Checkerboard: should be white (255,255,255) or light gray (204,204,204)
        assert px in ((255, 255, 255), (204, 204, 204))

    def test_opaque_pixel_renders_correct_color(self):
        """A fully opaque red pixel should render as pure red."""
        grid = PixelGrid(4, 4)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        img = build_render_image(grid, pixel_size=10, grid_settings=None)
        assert img.getpixel((5, 5)) == (255, 0, 0)

    def test_semi_transparent_pixel_blends_with_bg(self):
        """A 50% alpha white pixel over checkerboard should produce near-white."""
        grid = PixelGrid(4, 4)
        grid.set_pixel(0, 0, (255, 255, 255, 128))
        img = build_render_image(grid, pixel_size=10, grid_settings=None)
        r, g, b = img.getpixel((5, 5))
        # Blending white@128 over white or light gray -> should be >= 228
        assert r > 220
        assert r == g == b

    def test_pixel_size_1_produces_correct_dimensions(self):
        """At pixel_size=1, output should match grid dimensions exactly."""
        grid = PixelGrid(16, 8)
        img = build_render_image(grid, pixel_size=1, grid_settings=None)
        assert img.size == (16, 8)

    def test_grid_lines_drawn_when_enabled(self):
        """Grid lines should appear when grid_settings=GridSettings() and ps >= 4."""
        grid = PixelGrid(4, 4)
        img_no_grid = build_render_image(grid, pixel_size=10, grid_settings=None)
        img_with_grid = build_render_image(grid, pixel_size=10, grid_settings=GridSettings())
        assert img_no_grid.getpixel((10, 5)) != img_with_grid.getpixel((10, 5))

    def test_grid_lines_not_drawn_when_pixel_size_small(self):
        """Grid lines should not appear when pixel_size < 4."""
        grid = PixelGrid(4, 4)
        img_no_grid = build_render_image(grid, pixel_size=2, grid_settings=None)
        img_with_grid = build_render_image(grid, pixel_size=2, grid_settings=GridSettings())
        assert list(img_no_grid.getdata()) == list(img_with_grid.getdata())

    def test_onion_skin_tints_and_composites(self):
        """Onion skin should be visible as a tinted layer under empty current frame."""
        onion = PixelGrid(4, 4)
        onion.set_pixel(0, 0, (255, 0, 0, 255))
        grid = PixelGrid(4, 4)  # empty current frame
        img = build_render_image(grid, pixel_size=10, grid_settings=None,
                                 onion_grid=onion)
        r, g, b = img.getpixel((5, 5))
        # Onion tint: (255//2+128, 0//2+128, 0//2+128) = (255, 128, 128) at alpha 64
        # Composited over bg (43, 43, 43): red channel should dominate
        assert r > g
        assert r > b

    def test_onion_skin_mismatched_dimensions_ignored(self):
        """Onion grid with different dimensions should be safely ignored."""
        onion = PixelGrid(8, 8)
        onion.set_pixel(0, 0, (255, 0, 0, 255))
        grid = PixelGrid(4, 4)
        img = build_render_image(grid, pixel_size=10, grid_settings=None,
                                 onion_grid=onion)
        # Should just render checkerboard bg without crash
        px = img.getpixel((5, 5))
        assert px in ((255, 255, 255), (204, 204, 204))


class TestOnionSkinMultiFrame:
    def test_onion_skin_multi_frame(self):
        """build_render_image accepts onion_grids list instead of single onion_grid."""
        grid = PixelGrid(8, 8)
        past_1 = PixelGrid(8, 8)
        past_1.set_pixel(0, 0, (255, 0, 0, 255))
        past_2 = PixelGrid(8, 8)
        past_2.set_pixel(1, 1, (0, 255, 0, 255))

        # New signature: onion_past_grids, onion_future_grids
        img = build_render_image(
            grid, pixel_size=1, grid_settings=None,
            onion_past_grids=[past_1, past_2],
            onion_future_grids=[],
            onion_past_tint=(255, 0, 170),
            onion_future_tint=(0, 240, 255)
        )
        assert img is not None
        assert img.size == (8, 8)

    def test_old_onion_grid_still_works(self):
        """Backward compat: old onion_grid param still works."""
        grid = PixelGrid(4, 4)
        onion = PixelGrid(4, 4)
        onion.set_pixel(0, 0, (255, 0, 0, 255))
        img = build_render_image(grid, pixel_size=1, grid_settings=None,
                                 onion_grid=onion)
        r, g, b = img.getpixel((0, 0))
        assert r > g  # Should still show onion tint


class TestReferenceImageRendering:
    def test_reference_image_composites_at_position(self):
        """Reference image should appear at specified (x, y) position."""
        grid = PixelGrid(8, 8)
        ref_img = Image.new("RGBA", (2, 2), (255, 0, 0, 255))
        ref = ReferenceImage(image=ref_img, x=2, y=3, scale=1.0, opacity=1.0)
        img = build_render_image(grid, pixel_size=1, grid_settings=None,
                                 reference=ref)
        r, g, b = img.getpixel((2, 3))
        assert r == 255
        assert g == 0
        assert b == 0

    def test_reference_image_with_scale(self):
        """Reference image at scale=2.0 should cover 2x area in canvas pixels."""
        grid = PixelGrid(8, 8)
        ref_img = Image.new("RGBA", (2, 2), (0, 255, 0, 255))
        ref = ReferenceImage(image=ref_img, x=0, y=0, scale=2.0, opacity=1.0)
        img = build_render_image(grid, pixel_size=1, grid_settings=None,
                                 reference=ref)
        # (1, 1) is within scaled 4x4 area -> should be green
        r, g, b = img.getpixel((1, 1))
        assert g == 255
        # (5, 4) is outside scaled area -> should be checkerboard gray (204)
        r2, g2, b2 = img.getpixel((5, 4))
        assert g2 < 255

    def test_reference_image_with_opacity(self):
        """Reference image at reduced opacity should blend with background."""
        grid = PixelGrid(4, 4)
        ref_img = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
        ref = ReferenceImage(image=ref_img, x=0, y=0, scale=1.0, opacity=0.5)
        img = build_render_image(grid, pixel_size=1, grid_settings=None,
                                 reference=ref)
        # Check pixel (0, 1) which has gray (204) checkerboard bg
        # Red@50% over gray -> blended, not pure red
        r, g, b = img.getpixel((0, 1))
        assert 200 < r < 255
        assert g < r
        assert b < r

    def test_reference_none_renders_normally(self):
        """Passing reference=None should render identically to no reference."""
        grid = PixelGrid(4, 4)
        img_none = build_render_image(grid, pixel_size=1, grid_settings=None,
                                      reference=None)
        img_default = build_render_image(grid, pixel_size=1, grid_settings=None)
        assert list(img_none.getdata()) == list(img_default.getdata())

    def test_old_reference_image_param_still_works(self):
        """Backward compat: old reference_image + reference_opacity params."""
        grid = PixelGrid(4, 4)
        ref_img = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
        img = build_render_image(grid, pixel_size=1, grid_settings=None,
                                 reference_image=ref_img,
                                 reference_opacity=1.0)
        r, g, b = img.getpixel((0, 0))
        assert r == 255


class TestBuildFloatingImage:
    def test_floating_image_correct_size(self):
        source = PixelGrid(4, 3)
        source.set_pixel(0, 0, (255, 0, 0, 255))
        img = build_floating_image(source, pixel_size=10)
        assert img.size == (40, 30)

    def test_floating_image_has_transparency(self):
        source = PixelGrid(4, 3)
        source.set_pixel(0, 0, (255, 0, 0, 255))
        img = build_floating_image(source, pixel_size=10)
        assert img.mode == "RGBA"
        assert img.getpixel((15, 15))[3] == 0

    def test_floating_image_opaque_pixel(self):
        source = PixelGrid(4, 3)
        source.set_pixel(0, 0, (255, 0, 0, 255))
        img = build_floating_image(source, pixel_size=10)
        r, g, b, a = img.getpixel((5, 5))
        assert (r, g, b) == (255, 0, 0)
        assert a == 255
