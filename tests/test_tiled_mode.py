"""Tests for tiled/seamless drawing mode."""
import pytest
from src.pixel_data import PixelGrid


class TestWrapCoord:
    def test_wrap_x_mode(self):
        w, h = 16, 16
        assert 18 % w == 2
        assert -1 % w == 15

    def test_wrap_y_mode(self):
        w, h = 16, 16
        assert 20 % h == 4
        assert -3 % h == 13

    def test_wrap_both(self):
        w, h = 8, 8
        assert (10 % w, 10 % h) == (2, 2)

    def test_no_wrap_when_off(self):
        x, y = 20, 20
        assert (x, y) == (20, 20)

    def test_pen_wraps_on_tiled_canvas(self):
        from src.tools import PenTool
        grid = PixelGrid(16, 16)
        pen = PenTool()
        wx = 17 % 16
        pen.apply(grid, wx, 5, (255, 0, 0, 255))
        assert grid.get_pixel(1, 5) == (255, 0, 0, 255)

    def test_eraser_wraps_on_tiled_canvas(self):
        from src.tools import EraserTool
        grid = PixelGrid(8, 8)
        grid.set_pixel(0, 0, (255, 0, 0, 255))
        eraser = EraserTool()
        wx = 8 % 8
        eraser.apply(grid, wx, 0)
        assert grid.get_pixel(0, 0) == (0, 0, 0, 0)


class TestTiledRender:
    def test_tiled_render_3x_size(self):
        from src.canvas import build_render_image
        from src.pixel_data import PixelGrid
        grid = PixelGrid(8, 8)
        normal = build_render_image(grid, 4, None, tiled_mode="off")
        tiled = build_render_image(grid, 4, None, tiled_mode="both")
        assert normal.size == (32, 32)
        assert tiled.size == (96, 96)

    def test_tiled_x_only(self):
        from src.canvas import build_render_image
        from src.pixel_data import PixelGrid
        grid = PixelGrid(8, 8)
        tiled = build_render_image(grid, 4, None, tiled_mode="x")
        assert tiled.size == (96, 96)


import tkinter as tk
from src.canvas import PixelCanvas


class TestTiledScrollRegion:
    @pytest.fixture
    def canvas_setup(self):
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("Tk unavailable in this environment")
        root.withdraw()
        grid = PixelGrid(8, 8)
        canvas = PixelCanvas(root, grid, pixel_size=4)
        yield canvas, grid
        root.destroy()

    def test_scrollregion_default_no_tiling(self, canvas_setup):
        canvas, grid = canvas_setup
        sr = canvas.cget("scrollregion").split()
        w, h = int(float(sr[2])), int(float(sr[3]))
        assert w == 8 * 4
        assert h == 8 * 4

    def test_scrollregion_expands_with_tiling(self, canvas_setup):
        canvas, grid = canvas_setup
        canvas.set_tiled_mode("both")
        sr = canvas.cget("scrollregion").split()
        w, h = int(float(sr[2])), int(float(sr[3]))
        assert w == 8 * 4 * 3
        assert h == 8 * 4 * 3

    def test_scrollregion_resets_when_tiling_off(self, canvas_setup):
        canvas, grid = canvas_setup
        canvas.set_tiled_mode("both")
        canvas.set_tiled_mode("off")
        sr = canvas.cget("scrollregion").split()
        w, h = int(float(sr[2])), int(float(sr[3]))
        assert w == 8 * 4
        assert h == 8 * 4

    def test_scrollregion_x_mode(self, canvas_setup):
        canvas, grid = canvas_setup
        canvas.set_tiled_mode("x")
        sr = canvas.cget("scrollregion").split()
        w, h = int(float(sr[2])), int(float(sr[3]))
        assert w == 8 * 4 * 3
        assert h == 8 * 4 * 3

    def test_scroll_region_correct_after_zoom_with_tiling(self, canvas_setup):
        canvas, grid = canvas_setup
        canvas.set_tiled_mode("both")
        canvas.pixel_size = 8
        canvas._resize_canvas()
        sr = canvas.cget("scrollregion").split()
        w, h = int(float(sr[2])), int(float(sr[3]))
        assert w == 8 * 8 * 3
        assert h == 8 * 8 * 3

    def test_to_grid_coords_wraps_in_tiled_mode(self, canvas_setup):
        canvas, grid = canvas_setup  # 8x8 grid, ps=4
        canvas.set_tiled_mode("both")
        class FakeEvent:
            x = 36
            y = 36
        gx, gy = canvas._to_grid_coords(FakeEvent())
        assert 0 <= gx < 8
        assert 0 <= gy < 8
        assert gx == 9 % 8  # 1
        assert gy == 9 % 8  # 1
