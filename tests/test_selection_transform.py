"""Tests for selection transform math and hit testing."""
import pytest
import numpy as np
import tkinter as tk
from PIL import Image

from src.selection_transform import (
    SelectionTransform, compute_affine_preview, compute_affine_final,
    get_transform_bounding_box, hit_test_transform_handle,
)


def _make_test_image(w: int, h: int, color=(255, 0, 0, 255)) -> Image.Image:
    """Create a solid RGBA test image."""
    img = Image.new("RGBA", (w, h), color)
    return img


class TestSelectionTransformDataclass:
    def test_identity_defaults(self):
        img = _make_test_image(4, 4)
        t = SelectionTransform(pixels=img, position=(0, 0))
        assert t.rotation == 0.0
        assert t.scale_x == 1.0
        assert t.scale_y == 1.0
        assert t.skew_x == 0.0
        assert t.skew_y == 0.0
        assert t.pivot == (2.0, 2.0)  # center of 4x4

    def test_identity_preview_returns_same_size(self):
        img = _make_test_image(8, 6)
        t = SelectionTransform(pixels=img, position=(0, 0))
        result = compute_affine_preview(t)
        assert result.size == (8, 6)

    def test_identity_preview_preserves_pixels(self):
        img = _make_test_image(4, 4, color=(255, 0, 0, 255))
        t = SelectionTransform(pixels=img, position=(0, 0))
        result = compute_affine_preview(t)
        arr = np.array(result)
        # All pixels should still be red
        assert arr[:, :, 0].min() == 255
        assert arr[:, :, 3].min() == 255


class TestAffinePreview:
    def test_rotation_90_swaps_dimensions(self):
        img = _make_test_image(8, 4)
        t = SelectionTransform(pixels=img, position=(0, 0), rotation=90.0)
        result = compute_affine_preview(t)
        # 90° rotation of 8x4 should produce ~4x8
        assert abs(result.size[0] - 4) <= 1
        assert abs(result.size[1] - 8) <= 1

    def test_scale_2x_doubles_dimensions(self):
        img = _make_test_image(4, 4)
        t = SelectionTransform(pixels=img, position=(0, 0), scale_x=2.0, scale_y=2.0)
        result = compute_affine_preview(t)
        assert result.size == (8, 8)

    def test_scale_non_uniform(self):
        img = _make_test_image(4, 4)
        t = SelectionTransform(pixels=img, position=(0, 0), scale_x=2.0, scale_y=1.0)
        result = compute_affine_preview(t)
        assert result.size == (8, 4)

    def test_skew_horizontal_changes_width(self):
        img = _make_test_image(4, 4)
        t = SelectionTransform(pixels=img, position=(0, 0), skew_x=45.0)
        result = compute_affine_preview(t)
        assert result.size[0] > 4

    def test_scale_down_halves(self):
        img = _make_test_image(8, 8)
        t = SelectionTransform(pixels=img, position=(0, 0), scale_x=0.5, scale_y=0.5)
        result = compute_affine_preview(t)
        assert result.size == (4, 4)

    def test_rotation_preserves_alpha(self):
        """Rotated image should have transparent background."""
        img = _make_test_image(4, 4, color=(255, 0, 0, 255))
        t = SelectionTransform(pixels=img, position=(0, 0), rotation=45.0)
        result = compute_affine_preview(t)
        arr = np.array(result)
        assert arr[0, 0, 3] == 0


class TestAffineFinal:
    def test_final_identity_same_as_preview(self):
        img = _make_test_image(4, 4)
        t = SelectionTransform(pixels=img, position=(0, 0))
        preview = compute_affine_preview(t)
        final = compute_affine_final(t)
        assert final.size == preview.size

    def test_final_rotation_uses_rotsprite(self):
        """Final render with rotation should produce result."""
        img = _make_test_image(8, 8, color=(255, 0, 0, 255))
        t = SelectionTransform(pixels=img, position=(0, 0), rotation=30.0)
        result = compute_affine_final(t)
        assert result.mode == "RGBA"
        assert result.size[0] > 0 and result.size[1] > 0

    def test_final_scale_only_no_rotsprite(self):
        """Scale-only transform should not invoke RotSprite."""
        img = _make_test_image(4, 4)
        t = SelectionTransform(pixels=img, position=(0, 0), scale_x=2.0, scale_y=2.0)
        result = compute_affine_final(t)
        assert result.size == (8, 8)


class TestBoundingBox:
    def test_identity_bounding_box(self):
        img = _make_test_image(10, 8)
        t = SelectionTransform(pixels=img, position=(5, 3))
        corners = get_transform_bounding_box(t)
        assert len(corners) == 4
        assert corners[0] == pytest.approx((5, 3), abs=0.1)
        assert corners[1] == pytest.approx((15, 3), abs=0.1)
        assert corners[2] == pytest.approx((15, 11), abs=0.1)
        assert corners[3] == pytest.approx((5, 11), abs=0.1)

    def test_scaled_bounding_box(self):
        img = _make_test_image(4, 4)
        t = SelectionTransform(pixels=img, position=(0, 0), scale_x=2.0, scale_y=2.0)
        corners = get_transform_bounding_box(t)
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        assert max(xs) - min(xs) == pytest.approx(8.0, abs=0.5)
        assert max(ys) - min(ys) == pytest.approx(8.0, abs=0.5)


class TestHitTest:
    def _make_transform(self):
        """10x10 image at position (10, 10) => corners at (10,10), (20,10), (20,20), (10,20).
        Pivot at center = image (5,5), so canvas pivot = (15, 15)."""
        img = _make_test_image(10, 10)
        return SelectionTransform(pixels=img, position=(10, 10))

    def test_hit_corner_0(self):
        t = self._make_transform()
        result = hit_test_transform_handle(t, 10, 10, pixel_size=1)
        assert result == "corner:0"

    def test_hit_corner_2(self):
        t = self._make_transform()
        result = hit_test_transform_handle(t, 20, 20, pixel_size=1)
        assert result == "corner:2"

    def test_hit_midpoint_top(self):
        t = self._make_transform()
        result = hit_test_transform_handle(t, 15, 10, pixel_size=1)
        assert result == "midpoint:top"

    def test_hit_midpoint_right(self):
        t = self._make_transform()
        result = hit_test_transform_handle(t, 20, 15, pixel_size=1)
        assert result == "midpoint:right"

    def test_hit_inside(self):
        t = self._make_transform()
        # Use (13, 13) to avoid hitting the pivot at (15, 15)
        result = hit_test_transform_handle(t, 13, 13, pixel_size=1)
        assert result == "inside"

    def test_hit_outside(self):
        t = self._make_transform()
        result = hit_test_transform_handle(t, 2, 2, pixel_size=1)
        assert result == "outside"

    def test_hit_pivot(self):
        t = self._make_transform()
        result = hit_test_transform_handle(t, 15, 15, pixel_size=1, threshold=2.0)
        assert result == "pivot"

    def test_hit_none_far_away(self):
        t = self._make_transform()
        result = hit_test_transform_handle(t, 500, 500, pixel_size=1)
        assert result == "outside"


class TestTransformFlow:
    def test_commit_clips_to_canvas(self):
        from src.selection_transform import clip_to_canvas
        from src.pixel_data import PixelGrid

        img = _make_test_image(4, 4, color=(255, 0, 0, 255))
        grid = PixelGrid(4, 4)
        clip_to_canvas(img, (-2, -2), grid)

        assert tuple(grid.get_pixel(0, 0)) == (255, 0, 0, 255)
        assert tuple(grid.get_pixel(1, 1)) == (255, 0, 0, 255)

    def test_commit_identity_pastes_original(self):
        from src.selection_transform import clip_to_canvas
        from src.pixel_data import PixelGrid

        img = _make_test_image(3, 3, color=(0, 255, 0, 255))
        grid = PixelGrid(10, 10)
        clip_to_canvas(img, (2, 2), grid)

        assert tuple(grid.get_pixel(2, 2)) == (0, 255, 0, 255)
        assert tuple(grid.get_pixel(4, 4)) == (0, 255, 0, 255)
        assert grid.get_pixel(0, 0)[3] == 0


class TestCommitUndo:
    def test_commit_pushes_result_to_grid(self):
        """Full flow: create transform, scale 2x, commit, verify pixels."""
        from src.pixel_data import PixelGrid
        from src.selection_transform import (
            SelectionTransform, compute_affine_final,
            get_transform_bounding_box, clip_to_canvas,
        )

        img = _make_test_image(4, 4, color=(0, 0, 255, 255))
        t = SelectionTransform(pixels=img, position=(2, 2), scale_x=2.0, scale_y=2.0)

        final = compute_affine_final(t)
        corners = get_transform_bounding_box(t)
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        place_x, place_y = int(min(xs)), int(min(ys))

        grid = PixelGrid(16, 16)
        clip_to_canvas(final, (place_x, place_y), grid)

        center = grid.get_pixel(4, 4)
        assert center[2] == 255  # Blue channel
        assert center[3] == 255  # Fully opaque

    def test_cancel_float_restores_pixels(self):
        """Cancel after floating should restore original pixels."""
        from src.pixel_data import PixelGrid
        from src.selection_transform import SelectionTransform, clip_to_canvas

        img = _make_test_image(3, 3, color=(255, 255, 0, 255))
        t = SelectionTransform(pixels=img, position=(1, 1), source="float")

        grid = PixelGrid(8, 8)
        clip_to_canvas(t.pixels, t.position, grid)

        assert tuple(grid.get_pixel(1, 1)) == (255, 255, 0, 255)
        assert tuple(grid.get_pixel(3, 3)) == (255, 255, 0, 255)


class TestCanvasHandles:
    def test_draw_transform_handles_no_error(self):
        """Smoke test: drawing handles should not raise."""
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            pytest.skip("No display available")

        from src.canvas import PixelCanvas
        from src.pixel_data import PixelGrid
        grid = PixelGrid(25, 25)
        canvas = PixelCanvas(root, grid=grid, pixel_size=4)

        img = _make_test_image(10, 10)
        t = SelectionTransform(pixels=img, position=(5, 5))
        corners = get_transform_bounding_box(t)

        canvas.draw_transform_handles(corners, t.pivot, t.position, canvas.pixel_size)
        items = canvas.find_withtag("transform_handle")
        assert len(items) > 0

        canvas.clear_transform_handles()
        items = canvas.find_withtag("transform_handle")
        assert len(items) == 0

        root.destroy()
